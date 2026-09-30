import os, io, re, json, time, hashlib, mimetypes
import numpy as np
from PIL import Image, ImageOps
from dotenv import load_dotenv
from google import genai
from google.genai import types
from evidence import CheckResult, build_record

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM = """You are a warehouse prep-compliance inspector.
For EACH check return PASS, FAIL, or UNCERTAIN.
- PASS only when the images clearly show the requirement is met.
- FAIL only when the images clearly show it is NOT met.
- UNCERTAIN when the evidence is ambiguous, blurry, cropped, obscured or not shown. Never guess.
  UNCERTAIN is not a low-confidence PASS.
- Judge ONLY against the check definitions and reference rules given in the prompt.
  Do not use your own memory of Amazon's rules.
- Base every verdict ONLY on what is visible in the images.
- Never invent evidence. Describe exactly what you see and where (which image, which area).
Return ONLY valid JSON."""

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "rules", "amazon_prep_rules.md")
MAX_SIDE = int(os.getenv("IMAGE_MAX_SIDE", "1280"))   # photos are downscaled before sending


def load_rules():
    try:
        with open(RULES_PATH, encoding="utf-8") as f:
            text = f.read()
        return text, hashlib.sha256(text.encode("utf-8")).hexdigest()
    except OSError:
        return "", None


# ---- CATALOG: the six checks from the Prep Manager problem statement ----
CHECKS = {
    "polybag_sealed": "The product is inside a polybag and the polybag is fully sealed, with no "
                      "open edge or gap. FAIL if there is no polybag or it is open.",
    "suffocation_warning_ok": "A suffocation warning (text or icon) is present on the bag and fully "
                              "legible: not folded, creased, covered by a label or cut off. FAIL if "
                              "it is missing or obscured; say which in the reason.",
    "fnsku_label_ok": "An FNSKU label with an intact, unobstructed, scannable barcode is present on "
                      "the exterior, on a flat surface: not across a seam, fold, corner or curved "
                      "edge. FAIL if the label is missing, damaged or badly placed; say which in "
                      "the reason.",
    "original_barcode_covered": "The original manufacturer barcode is covered or not visible. FAIL "
                                "if an original barcode is still visible and could be scanned.",
    "expiry_date_legible": "The expiry date is printed, legible and not covered or cut off after "
                           "wrapping.",
    "handling_marks_present": "All required handling marks are visible and legible.",
}
PACKAGING_CHECKS = {
    "polybag":   ["polybag_sealed", "suffocation_warning_ok", "fnsku_label_ok",
                  "original_barcode_covered"],
    "glass_box": ["fnsku_label_ok", "original_barcode_covered"],
    "other":     ["fnsku_label_ok", "original_barcode_covered"],
}
CATEGORY_CHECKS = {   # extra checks a category adds on top of the packaging checks
    "general": [],
    "expiry_goods (food, supplements, cosmetics)": ["expiry_date_legible"],
    "fragile_goods": [],
    "baby_kids": ["suffocation_warning_ok"],
}
DEFAULT_MARKS = {"fragile_goods": ["fragile"]}   # marks a category requires by default
TYPE_CHECK = "packaging_matches_declared"
INSTR_CHECK = "client_instructions_followed"
QUALITY_CHECK = "image_quality"
VALID = {"PASS", "FAIL", "UNCERTAIN"}
_dead = set()
_chain_cache = None

# Quality gate thresholds. Tune on a few DEV photos, NOT on your evaluation photos.
BLUR_MIN, DARK_MAX, BRIGHT_MIN = 60.0, 40.0, 225.0


def resolve_marks(category, required_marks=None):
    return list(required_marks or DEFAULT_MARKS.get(category, []))


def build_check_keys(packaging, category, required_marks=None):
    keys = list(PACKAGING_CHECKS[packaging])
    for k in CATEGORY_CHECKS[category]:
        if k not in keys:
            keys.append(k)
    if resolve_marks(category, required_marks) and "handling_marks_present" not in keys:
        keys.append("handling_marks_present")
    return keys


def check_text(key, marks):
    if key == "handling_marks_present" and marks:
        return (f"All required handling marks ({', '.join(marks)}) are visible and legible. "
                f"FAIL if any required mark is missing.")
    return CHECKS[key]


def assess_images(image_paths):
    out = []
    for p in image_paths:
        name = os.path.basename(p)
        try:
            g = Image.open(p).convert("L")
            g.thumbnail((800, 800))
            a = np.asarray(g, dtype=np.float32)
            lap = (-4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1]
                   + a[1:-1, :-2] + a[1:-1, 2:])
            sharp, bright = float(lap.var()), float(a.mean())
        except Exception:
            out.append({"name": name, "ok": False, "issue": "unreadable"})
            continue
        issue = None
        if sharp < BLUR_MIN:
            issue = "blurry"
        elif bright < DARK_MAX:
            issue = "too dark"
        elif bright > BRIGHT_MIN:
            issue = "overexposed"
        out.append({"name": name, "sharpness": round(sharp, 1),
                    "brightness": round(bright, 1), "ok": issue is None, "issue": issue})
    return out


# ------------------------------ models ------------------------------
def _rank(name):
    """Full models before lite ones; newest version first ('flash-latest' aliases first)."""
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    ver = float(m.group(1)) if m else 99.0
    return ("lite" in name, -ver, name)


def discover_models():
    found = []
    try:
        for m in client.models.list():
            if "generateContent" in (m.supported_actions or []) and "flash" in m.name:
                name = m.name.replace("models/", "")
                if not any(x in name for x in ("image", "live", "tts", "audio", "embedding", "omni")):
                    found.append(name)
    except Exception:
        pass
    return sorted(found, key=_rank) or ["gemini-flash-latest", "gemini-flash-lite-latest"]


def model_chain():
    global _chain_cache
    env = os.getenv("GEMINI_MODELS")
    if env:
        chain = [m.strip() for m in env.split(",") if m.strip()]
    else:
        if _chain_cache is None:      # ask the API once, not on every inspection
            _chain_cache = discover_models()
        chain = _chain_cache
    return [m for m in chain if m not in _dead]


THINKING_LEVEL = os.getenv("THINKING_LEVEL", "").strip().lower()   # minimal | low | medium | high; empty = model default


def _call(model, parts):
    cfg = dict(system_instruction=SYSTEM, response_mime_type="application/json")
    if THINKING_LEVEL and model.startswith("gemini-3"):
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level=THINKING_LEVEL)
    return client.models.generate_content(
        model=model, contents=parts, config=types.GenerateContentConfig(**cfg))


def _usage(resp):
    um = getattr(resp, "usage_metadata", None)
    if not um:
        return None
    return {"prompt_tokens": getattr(um, "prompt_token_count", None),
            "output_tokens": getattr(um, "candidates_token_count", None),
            "thinking_tokens": getattr(um, "thoughts_token_count", None)}


MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "2"))
RETRY_WAIT = float(os.getenv("RETRY_WAIT", "3"))
_attempts = []


def _generate_json(parts, rounds=None):
    """Try each model in turn; if they are busy (503/429), wait briefly and go round again.
    Returns (parsed_json_or_None, model_used, latency_ms_of_successful_call, last_error, usage).
    Every attempt is recorded in _attempts so the evidence record can show where time went."""
    rounds = rounds or MAX_ROUNDS
    _attempts.clear()
    last_err = None
    for r in range(rounds):
        busy = False
        for model in model_chain():
            t0 = time.perf_counter()
            try:
                resp = _call(model, parts)
                raw = json.loads(resp.text)
                ms = int((time.perf_counter() - t0) * 1000)
                _attempts.append({"model": model, "ms": ms, "ok": True})
                return raw, model, ms, None, _usage(resp)
            except Exception as e:
                msg = str(e)
                _attempts.append({"model": model, "ms": int((time.perf_counter() - t0) * 1000),
                                  "ok": False, "error": msg[:120]})
                last_err = f"{model}: {msg[:200]}"
                if "404" in msg or "NOT_FOUND" in msg:
                    _dead.add(model)
                elif any(x in msg for x in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                    busy = True
        if not busy:
            break
        time.sleep(RETRY_WAIT * (r + 1))
    return None, "none", 0, last_err, None

def _for_model(path):
    """Return (original_bytes, bytes_to_send, mime). Originals are what get hashed and stored."""
    with open(path, "rb") as f:
        original = f.read()
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(original))).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        return original, buf.getvalue(), "image/jpeg"
    except Exception:
        return original, original, mimetypes.guess_type(path)[0] or "image/jpeg"


def load_images(image_paths):
    parts, images = [], {}
    for i, p in enumerate(image_paths, 1):
        original, sent, mime = _for_model(p)
        name = os.path.basename(p)
        images[name] = original
        parts.append(f"Image {i} ({name}):")
        parts.append(types.Part.from_bytes(data=sent, mime_type=mime))
    return parts, images


def detect_packaging(image_paths):
    parts, _ = load_images(image_paths)
    parts.append(f"""What packaging does the product have? Choose exactly one of:
{list(PACKAGING_CHECKS)} or "unknown" if unclear.
Return JSON: {{"packaging":"<choice>"}}""")
    raw, _, _, _, _ = _generate_json(parts, rounds=2)
    if isinstance(raw, list):
        raw = raw[0] if raw and isinstance(raw[0], dict) else {}
    choice = raw.get("packaging", "unknown") if isinstance(raw, dict) else "unknown"
    return choice if choice in PACKAGING_CHECKS else "unknown"


def run_agent(image_paths, packaging, category="general", instructions="",
              subject="unit_1", operator="operator_1", required_marks=None):
    if packaging not in PACKAGING_CHECKS:
        raise ValueError(f"Unknown packaging '{packaging}'. Choose from {list(PACKAGING_CHECKS)}")
    if category not in CATEGORY_CHECKS:
        raise ValueError(f"Unknown category '{category}'. Choose from {list(CATEGORY_CHECKS)}")
    instructions = (instructions or "").strip()
    marks = resolve_marks(category, required_marks)

    keys = build_check_keys(packaging, category, marks)
    lines = [f"- {k}: {check_text(k, marks)}" for k in keys]
    keys.append(TYPE_CHECK)
    lines.append(f"- {TYPE_CHECK}: The product's packaging matches the declared type "
                 f"'{packaging}'. FAIL if it clearly is a different type, UNCERTAIN if not visible.")
    if instructions:
        keys.append(INSTR_CHECK)
        lines.append(f"- {INSTR_CHECK}: The photos show the unit prepped according to these "
                     f"client instructions: \"{instructions}\". FAIL if visibly not followed, "
                     f"UNCERTAIN if it cannot be seen.")

    parts, images = load_images(image_paths)
    quality = assess_images(image_paths)
    bad = [q for q in quality if not q["ok"]]
    all_bad = len(bad) == len(quality)
    bad_txt = ", ".join(f"{q['name']} ({q['issue']})" for q in bad)
    rules_text, rules_sha = load_rules()

    results = []
    if all_bad:
        results.append(CheckResult(QUALITY_CHECK, "UNCERTAIN", 1.0,
                       f"All photos failed the quality gate: {bad_txt}. Retake in better light, "
                       f"in focus.", "local_quality_gate", 0))
    else:
        note = f"{len(bad)} of {len(quality)} photos flagged: {bad_txt}." if bad else "All photos passed."
        results.append(CheckResult(QUALITY_CHECK, "PASS", 1.0, note, "local_quality_gate", 0))

    raw, used, latency_ms, last_err, usage = None, "none", 0, None, None
    t_all = time.perf_counter()
    if all_bad:
        used, last_err = "quality_gate", f"Model not called: photos unusable ({bad_txt})."
    else:
        prompt = "Checks to perform (use these exact ids):\n" + "\n".join(lines)
        if rules_text:
            prompt += ("\n\nReference rules (source text; judge ONLY against these rules and the "
                       "check definitions above, not against your own memory):\n" + rules_text)
        if bad:
            prompt += (f"\n\nA local quality check flagged: {bad_txt}. Treat details visible "
                       f"only in flagged photos as UNCERTAIN.")
        prompt += ('\n\nReturn JSON: {"checks":[{"check":"<id>","verdict":"PASS|FAIL|UNCERTAIN",'
                   '"reason":"...","evidence":"...","confidence":0.0}]}')
        parts.append(prompt)
        raw, used, latency_ms, last_err, usage = _generate_json(parts)
        if raw is None and not last_err:
            last_err = "No model available for this key."
    total_ms = int((time.perf_counter() - t_all) * 1000)
    pending = raw is None and not all_bad     # fail open: still produce a record

    # The model sometimes answers with a bare list instead of {"checks": [...]}
    if isinstance(raw, list):
        raw = {"checks": raw}
    elif isinstance(raw, dict) and not isinstance(raw.get("checks"), list):
        raw = {"checks": next((v for v in raw.values() if isinstance(v, list)), [])}
    elif not isinstance(raw, dict):
        raw = {"checks": []}
    by_key = {(c.get("check") or c.get("check_key")): c
              for c in raw.get("checks", []) if isinstance(c, dict)}

    for key in keys:
        c = by_key.get(key)
        if c and c.get("verdict") in VALID:
            try:
                conf = max(0.0, min(1.0, float(c.get("confidence", 0))))
            except (TypeError, ValueError):
                conf = 0.0
            detail = f"{c.get('reason', '')} | Evidence: {c.get('evidence', '')}"
            verdict = c["verdict"]
        else:
            verdict, conf = "UNCERTAIN", 0.0
            detail = f"No valid model output. {last_err or 'Check missing from response.'}"
        results.append(CheckResult(key, verdict, conf, detail, used, latency_ms))

    return build_record(subject, results, images, operator=operator,
                        context={"packaging": packaging, "category": category,
                                 "instructions": instructions, "required_marks": marks,
                                 "photo_quality": quality,
                                 "rules_source": "rules/amazon_prep_rules.md",
                                 "rules_sha256": rules_sha,
                                 "image_max_side": MAX_SIDE,
                                 "usage": usage, "total_ms": total_ms,
                                 "pending": pending,
                                 "model_error": last_err if pending else None})


if __name__ == "__main__":
    import sys
    photo = sys.argv[1] if len(sys.argv) > 1 else "photo1.jpg"
    pack = sys.argv[2] if len(sys.argv) > 2 else "polybag"
    cat = sys.argv[3] if len(sys.argv) > 3 else "general"
    print(json.dumps(run_agent([photo], pack, cat), indent=2))