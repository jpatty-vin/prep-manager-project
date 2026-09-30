"""
Evidence record for the Prep Manager agent.

One record = one inspected unit: the images (by hash), every per-check verdict with the
model that produced it, the overall outcome (who decided, when), human overrides, and a
content hash so any later change is detectable.

Compatible with the earlier version: CheckResult, Override, EvidenceRecord, rollup,
build_record(...) and add_override(...) keep their names and argument order.
"""
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# Confirm both values against the official track repo's README/RULES. Change them here only.
SCHEMA_VERSION = "1.0"
AGENT_NAME = "prep"

VERDICTS = ("PASS", "FAIL", "UNCERTAIN")
NON_MODEL = {"local_quality_gate", "quality_gate", "none"}
IMAGE_DIR = os.path.join(os.getenv("EVIDENCE_DIR", "records"), "images")


@dataclass
class CheckResult:
    check_key: str            # e.g. "polybag_sealing"
    verdict: str              # "PASS" | "FAIL" | "UNCERTAIN"
    confidence: float         # 0..1 (the model's own estimate, not calibrated)
    detail: str               # reason + what was seen in the image
    model_version: str        # the model actually used for THIS check
    latency_ms: int


@dataclass
class Override:
    check_key: str
    original_verdict: str     # the verdict in force just before this override
    new_verdict: str
    reason_code: str          # e.g. "MODEL_WRONG", "BAD_PHOTO", "OTHER"
    reason_text: str
    operator_label: str
    at: str
    previous_hash: str = ""   # content_hash before this override (simple hash chain)


@dataclass
class EvidenceRecord:
    record_id: str
    schema_version: str
    organization_id: str
    client_id: str
    agent: str
    subject: str              # plain unit / FNSKU / item id
    captured_at: str
    operator_label: str
    images: list              # [{"name", "sha256", "bytes", "stored_path"}]
    checks: list              # list of CheckResult dicts
    outcome: dict             # {"decision", "decided_by", "decided_at"}
    overrides: list = field(default_factory=list)
    status: str = "final"     # "final" | "needs_review" | "overridden"
    content_hash: str = ""
    context: dict = field(default_factory=dict)   # packaging, category, instructions (extra field)


# ----------------------------------------------------------------------------
def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "content_hash"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def verify_record(rec: dict) -> bool:
    """True if the record has not changed since its hash was computed."""
    return rec.get("content_hash") == _hash(rec)


def rollup(checks):
    """checks = list of dicts with a 'verdict'. Any FAIL -> FAIL, else any UNCERTAIN -> UNCERTAIN, else PASS."""
    v = [c["verdict"] for c in checks]
    if "FAIL" in v:
        return "FAIL"
    if "UNCERTAIN" in v:
        return "UNCERTAIN"
    return "PASS"


def effective_verdicts(rec: dict) -> dict:
    """Verdict per check after human overrides (the latest override for a check wins)."""
    eff = {c["check_key"]: c["verdict"] for c in rec["checks"]}
    for o in rec.get("overrides", []):
        eff[o["check_key"]] = o["new_verdict"]
    return eff


def decision_of(rec: dict) -> str:
    """Overall PASS/FAIL/UNCERTAIN. Also reads old records where outcome was a plain string."""
    out = rec.get("outcome")
    return out.get("decision", "") if isinstance(out, dict) else (out or "")


def _refresh(rec: dict) -> dict:
    eff = effective_verdicts(rec)
    rec["outcome"]["decision"] = rollup([{"verdict": v} for v in eff.values()])
    if rec["overrides"]:
        rec["status"] = "overridden"
    elif rec["outcome"]["decision"] == "UNCERTAIN":
        rec["status"] = "needs_review"
    else:
        rec["status"] = "final"
    rec["content_hash"] = _hash(rec)
    return rec


def _store_image(name, digest, data):
    """Keep a copy of the image, named by its hash, so the record can be reconstructed later."""
    try:
        os.makedirs(IMAGE_DIR, exist_ok=True)
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        path = os.path.join(IMAGE_DIR, digest + ext)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(data)
        return path.replace("\\", "/")
    except OSError:
        return ""


def build_record(subject, checks, image_bytes_by_name, org="org_demo",
                 client="client_demo", operator="operator_1", context=None,
                 store_images=True) -> dict:
    check_dicts = [asdict(c) if isinstance(c, CheckResult) else dict(c) for c in checks]

    images = []
    for name, data in image_bytes_by_name.items():
        digest = hashlib.sha256(data).hexdigest()
        meta = {"name": name, "sha256": digest, "bytes": len(data)}
        if store_images:
            meta["stored_path"] = _store_image(name, digest, data)
        images.append(meta)

    model = next((c["model_version"] for c in check_dicts if c["model_version"] not in NON_MODEL),
                 check_dicts[0]["model_version"] if check_dicts else "none")
    now = _now()

    rec = asdict(EvidenceRecord(
        record_id=str(uuid.uuid4()),
        schema_version=SCHEMA_VERSION,
        organization_id=org, client_id=client, agent=AGENT_NAME,
        subject=subject,
        captured_at=now,
        operator_label=operator,
        images=images,
        checks=check_dicts,
        outcome={"decision": "", "decided_by": f"agent:{model}", "decided_at": now},
        context=context or {},
    ))
    return _refresh(rec)


def add_override(rec: dict, check_key, new_verdict, reason_code,
                 reason_text, operator) -> dict:
    """Add a human override. Changes rec in place AND returns it. The reason is required."""
    new_verdict = str(new_verdict).strip().upper()
    if new_verdict not in VERDICTS:
        raise ValueError(f"New verdict must be one of {VERDICTS}")
    if not str(reason_text).strip():
        raise ValueError("Override requires a reason")
    if check_key not in [c["check_key"] for c in rec["checks"]]:
        raise ValueError(f"Unknown check: {check_key}")

    rec["overrides"].append(asdict(Override(
        check_key=check_key,
        original_verdict=effective_verdicts(rec)[check_key],
        new_verdict=new_verdict,
        reason_code=reason_code or "OTHER",
        reason_text=str(reason_text).strip(),
        operator_label=operator,
        at=_now(),
        previous_hash=rec["content_hash"],
    )))
    rec["outcome"]["decided_by"] = f"human:{operator}"
    rec["outcome"]["decided_at"] = _now()
    return _refresh(rec)   # recomputes the overall decision, status and hash


def save_record(rec: dict, folder=None) -> str:
    folder = folder or os.getenv("EVIDENCE_DIR", "records")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, rec["record_id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)
    return path