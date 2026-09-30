import os, json, glob, tempfile
import pandas as pd
import streamlit as st
from prep_agent import (PACKAGING_CHECKS, CATEGORY_CHECKS, TYPE_CHECK, detect_packaging,
                        run_agent)
from evidence import (add_override, rollup, decision_of, effective_verdicts,
                      verify_record, save_record)

st.set_page_config(page_title="Prep Manager Agent", layout="wide")
RECORD_DIR = os.getenv("EVIDENCE_DIR", "records")
os.makedirs(RECORD_DIR, exist_ok=True)
ICON = {"PASS": "✅", "FAIL": "❌", "UNCERTAIN": "❓"}
REASONS = ["MODEL_WRONG", "BAD_PHOTO", "RULE_EXCEPTION", "OTHER"]
NOT_SURE = "Not sure - detect from photo"


def save_uploads(files):
    d, paths = tempfile.mkdtemp(), []
    for i, f in enumerate(files):
        name = getattr(f, "name", None) or "camera.jpg"
        p = os.path.join(d, f"{i}_{os.path.basename(name)}")
        with open(p, "wb") as out:
            out.write(f.getvalue())
        paths.append(p)
    return paths


page = st.sidebar.radio("Page", ["Inspect", "History", "Evaluation"])
st.sidebar.header("Session")
operator = st.sidebar.text_input("Operator label", "operator_1")
subject = st.sidebar.text_input("Unit / FNSKU / item id", "unit_1")
st.sidebar.caption("Every result is saved as a JSON evidence record in ./records")


# =============================== INSPECT ===============================
def inspect_page():
    st.title("Prep Manager Agent")
    st.caption("Photos in → per-check decision with evidence out. UNCERTAIN is its own outcome: "
               "a confident answer from a bad photo is worse than no answer.")
    left, right = st.columns([1, 1.4])

    with left:
        st.subheader("1. Input")
        files = list(st.file_uploader("Upload photos of the unit", type=["jpg", "jpeg", "png"],
                                      accept_multiple_files=True) or [])
        with st.expander("Or take a photo with the camera (optional)"):
            cam = st.camera_input("Camera")
            if cam:
                files.append(cam)
        for f in files:
            st.image(f.getvalue(), caption=getattr(f, "name", "camera"), width="stretch")

        category = st.selectbox("Product category", list(CATEGORY_CHECKS))
        instructions = st.text_area("Prep instructions from the client (optional)",
                                    placeholder="e.g. Bubble-wrap the unit, place FNSKU on the front panel")

        choice = st.selectbox("What type of packaging is this product?",
                              [NOT_SURE] + list(PACKAGING_CHECKS))
        packaging = choice
        if choice == NOT_SURE:
            if st.button("Detect packaging from photo", disabled=not files):
                with st.spinner("Looking at the photo..."):
                    st.session_state["detected"] = detect_packaging(save_uploads(files))
            detected = st.session_state.get("detected")
            if detected:
                options = list(PACKAGING_CHECKS)
                if detected in options:
                    st.info(f"Looks like: **{detected}**. Confirm or change:")
                else:
                    st.warning("Couldn't tell the packaging type. Please choose one.")
                packaging = st.selectbox("Confirmed packaging type", options,
                                         index=options.index(detected) if detected in options else 0)
            else:
                packaging = None

        if st.button("Run inspection", type="primary", disabled=not files or not packaging):
            try:
                with st.spinner("Inspecting... (can take up to a minute if the models are busy)"):
                    rec = run_agent(save_uploads(files), packaging, category=category,
                                    instructions=instructions, subject=subject, operator=operator)
                    save_record(rec)
                    st.session_state["rec"] = rec
            except Exception as e:
                st.error(f"The inspection failed: {str(e)[:300]}")

    with right:
        st.subheader("2. Decision and evidence")
        rec = st.session_state.get("rec")
        if not rec:
            st.write("Upload photos, choose category and packaging, then run the inspection.")
            return

        eff = effective_verdicts(rec)          # verdicts after human overrides
        overall = decision_of(rec)             # overall PASS / FAIL / UNCERTAIN
        agent_overall = rollup(rec["checks"])  # what the agent alone concluded
        banner = f"{ICON[overall]} Overall: **{overall}**"
        if overall != agent_overall:
            banner += f"  (agent said {agent_overall}, changed by override)"
        {"PASS": st.success, "FAIL": st.error, "UNCERTAIN": st.warning}[overall](banner)

        model_check = next((c for c in rec["checks"] if c["check_key"] != "image_quality"),
                           rec["checks"][0])
        st.caption(f"Record {rec['record_id'][:8]} · model {model_check['model_version']} · "
                   f"{model_check['latency_ms']} ms · status {rec['status']} · "
                   f"decided by {rec['outcome']['decided_by']} · "
                   f"hash {rec['content_hash'][:12]}... "
                   f"{'✔ verified' if verify_record(rec) else '✘ MODIFIED'}")

        if eff.get(TYPE_CHECK) == "FAIL":
            st.error("The photo does not match the declared packaging type. "
                     "Other results are not reliable.")

        for c in rec["checks"]:
            key = c["check_key"]
            verdict = eff[key]
            changed = verdict != c["verdict"]
            with st.container(border=True):
                head = f"**{key}**  ·  "
                head += (f"~~{c['verdict']}~~ → {ICON[verdict]} **{verdict}**" if changed
                         else f"{ICON[verdict]} **{verdict}**")
                st.markdown(head + f"  ·  confidence {c['confidence']:.2f}")
                if verdict == "UNCERTAIN" and not changed:
                    st.markdown("<div style='border:2px dashed #999;padding:8px;border-radius:6px'>"
                                "Not enough visible evidence to decide.</div>",
                                unsafe_allow_html=True)
                st.write(c["detail"])
                with st.expander("Override this check"):
                    with st.form(f"ov_{rec['record_id'][:8]}_{key}"):
                        new_v = st.selectbox("New verdict", ["PASS", "FAIL", "UNCERTAIN"])
                        code = st.selectbox("Reason code", REASONS)
                        text = st.text_area("Reason (required)")
                        if st.form_submit_button("Apply override"):
                            try:
                                add_override(rec, key, new_v, code, text, operator)
                                save_record(rec)
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

        if rec["overrides"]:
            st.markdown("**Overrides recorded**")
            st.dataframe(rec["overrides"], width="stretch")
        with st.expander("Full evidence record (JSON)"):
            st.json(rec)
        st.download_button("Download record", json.dumps(rec, indent=2),
                           file_name=f"{rec['record_id']}.json", mime="application/json")


# =============================== HISTORY ===============================
def history_page():
    st.title("Evidence history")
    recs = []
    for p in glob.glob(os.path.join(RECORD_DIR, "*.json")):
        try:
            with open(p) as f:
                recs.append(json.load(f))
        except Exception:
            continue
    if not recs:
        st.info("No records yet. Run an inspection first.")
        return
    recs.sort(key=lambda r: r.get("captured_at", ""), reverse=True)

    def by(r):
        out = r.get("outcome")
        return out.get("decided_by", "") if isinstance(out, dict) else ""

    def intact(r):
        try:
            return "✔" if verify_record(r) else "✘"
        except Exception:
            return "?"

    st.dataframe(pd.DataFrame([{
        "record": r["record_id"][:8], "captured_at": r.get("captured_at", "")[:19],
        "subject": r.get("subject", ""), "operator": r.get("operator_label", ""),
        "outcome": decision_of(r), "decided_by": by(r), "status": r.get("status", ""),
        "overrides": len(r.get("overrides", [])), "hash": intact(r),
    } for r in recs]), width="stretch")
    pick = st.selectbox("Open a record", [r["record_id"] for r in recs])
    st.json(next(r for r in recs if r["record_id"] == pick))


# ============================== EVALUATION =============================
def evaluation_page():
    st.title("Evaluation results")
    if not os.path.exists("eval/summary.csv"):
        st.info("Run `python evaluate.py run` then `python evaluate.py score` first.")
        return
    if os.path.exists("eval/metrics.json"):
        m = json.load(open("eval/metrics.json"))
        cols = st.columns(4)
        cols[0].metric("Units evaluated", m["n_images"])
        cols[1].metric("Labeler kappa (A vs B)", m["labeler_kappa"])
        cols[2].metric("Overall UNCERTAIN rate", f"{m['uncertain_rate']:.0%}")
        cols[3].metric("Latency p50 / p95 (ms)", f"{m['latency_p50']} / {m['latency_p95']}")
    st.subheader("Per-check results (never blended)")
    st.dataframe(pd.read_csv("eval/summary.csv"), width="stretch")
    if os.path.exists("eval/failures.csv"):
        st.subheader("Failure cases")
        st.dataframe(pd.read_csv("eval/failures.csv"), width="stretch")


{"Inspect": inspect_page, "History": history_page, "Evaluation": evaluation_page}[page]()