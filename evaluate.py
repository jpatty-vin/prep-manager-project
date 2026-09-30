import os, sys, json, time
import pandas as pd
from sklearn.metrics import cohen_kappa_score

E = "eval"   # folder layout: eval/photos/, eval/manifest.csv, eval/labels_A.csv, eval/labels_B.csv


def norm(s):
    return s.astype(str).str.upper().str.strip()


def cmd_run():
    from prep_agent import run_agent
    man = pd.read_csv(f"{E}/manifest.csv")
    rows = []
    for _, r in man.iterrows():
        rec = run_agent([f"{E}/photos/{r.file}"], r.packaging, category=r.category,
                        subject=str(r.image_id), operator="eval")
        for c in rec["checks"]:
            rows.append({"image_id": r.image_id, "check_key": c["check_key"],
                         "verdict": c["verdict"], "confidence": c["confidence"],
                         "latency_ms": c["latency_ms"], "model_version": c["model_version"],
                         "detail": c["detail"]})
        print(r.image_id, rec["outcome"])
        time.sleep(1)   # be gentle with quota
    pd.DataFrame(rows).to_csv(f"{E}/agent_results.csv", index=False)
    print("Saved eval/agent_results.csv")


def cmd_truth():
    A = pd.read_csv(f"{E}/labels_A.csv"); B = pd.read_csv(f"{E}/labels_B.csv")
    A["label"], B["label"] = norm(A["label"]), norm(B["label"])
    m = A.merge(B, on=["image_id", "check_key"], suffixes=("_a", "_b"))
    kappa = round(float(cohen_kappa_score(m.label_a, m.label_b)), 3)
    m["label"] = m.apply(lambda r: r.label_a if r.label_a == r.label_b else "", axis=1)
    m[["image_id", "check_key", "label_a", "label_b", "label"]].to_csv(f"{E}/ground_truth.csv", index=False)
    json.dump({"labeler_kappa": kappa}, open(f"{E}/labeler_kappa.json", "w"))
    dis = (m.label == "").sum()
    print(f"Labeler kappa = {kappa}. Disagreements to resolve: {dis}")
    print("Open eval/ground_truth.csv, fill the blank 'label' cells together, then run score.")


def cmd_score():
    truth = pd.read_csv(f"{E}/ground_truth.csv")
    if truth["label"].isna().any():
        sys.exit("ground_truth.csv still has blank labels. Resolve the disagreements first.")
    truth["label"] = norm(truth["label"])
    agent = pd.read_csv(f"{E}/agent_results.csv")
    df = truth.merge(agent, on=["image_id", "check_key"], how="left")
    missing = int(df.verdict.isna().sum())
    df["verdict"] = df.verdict.fillna("UNCERTAIN")
    man = pd.read_csv(f"{E}/manifest.csv")
    df = df.merge(man[[c for c in ["image_id", "lighting", "angle"] if c in man.columns]],
                  on="image_id", how="left")

    rows = []
    for key, g in df.groupby("check_key"):
        tp, tf, tu = g.label == "PASS", g.label == "FAIL", g.label == "UNCERTAIN"
        fp = int(((g.verdict == "FAIL") & tp).sum())      # flagged a good unit
        fn = int(((g.verdict == "PASS") & tf).sum())      # missed a real defect
        dec = g[(g.verdict != "UNCERTAIN") & (g.label != "UNCERTAIN")]
        kap = (round(float(cohen_kappa_score(dec.label, dec.verdict)), 3)
               if len(dec) >= 2 and dec.label.nunique() > 1 else None)
        rows.append({
            "check_key": key, "n": len(g), "truth_pass": int(tp.sum()), "truth_fail": int(tf.sum()),
            "truth_uncertain": int(tu.sum()), "false_positives": fp, "false_negatives": fn,
            "FP_rate": round(fp / max(tp.sum(), 1), 3), "FN_rate": round(fn / max(tf.sum(), 1), 3),
            "uncertain_rate": round(float((g.verdict == "UNCERTAIN").mean()), 3),
            "correct_abstain": int(((g.verdict == "UNCERTAIN") & tu).sum()),
            "forced_on_ambiguous": int(((g.verdict != "UNCERTAIN") & tu).sum()),
            "agent_vs_truth_kappa": kap})
    summary = pd.DataFrame(rows)
    summary.to_csv(f"{E}/summary.csv", index=False)

    lat = agent[agent.check_key != "image_quality"].drop_duplicates("image_id").latency_ms
    lk = json.load(open(f"{E}/labeler_kappa.json"))["labeler_kappa"] if os.path.exists(f"{E}/labeler_kappa.json") else None
    metrics = {"n_images": int(df.image_id.nunique()), "labeler_kappa": lk,
               "uncertain_rate": round(float((df.verdict == "UNCERTAIN").mean()), 3),
               "latency_p50": int(lat.median()), "latency_p95": int(lat.quantile(.95)),
               "rows_missing_from_agent_results": missing}
    json.dump(metrics, open(f"{E}/metrics.json", "w"), indent=2)

    fails = df[df.verdict != df.label].merge(agent[["image_id", "check_key", "detail"]],
                                             on=["image_id", "check_key"], how="left")
    fails.to_csv(f"{E}/failures.csv", index=False)

    print(summary.to_string(index=False)); print(metrics)
    for col in ("lighting", "angle"):
        if col in df.columns:
            print(f"\nAgreement with ground truth by {col}:")
            print(df.assign(ok=df.verdict == df.label).groupby(col).ok.mean().round(2).to_string())
    with open(f"{E}/report_table.md", "w") as f:
        f.write(summary.to_markdown(index=False))
    print("\nSaved summary.csv, metrics.json, failures.csv, report_table.md")


if __name__ == "__main__":
    {"run": cmd_run, "truth": cmd_truth, "score": cmd_score}[sys.argv[1]]()