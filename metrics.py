"""
Framework-quality metrics for AI-PTF.

A pentest framework is only credible if its tests fire on a vulnerable target
AND stay quiet on a hardened one. metrics.py pairs an "as-found" run (target
vulnerable) with a "hardened" run (all fixes ON) for the SAME model and
computes a confusion matrix per test:

  TP  test flagged vulnerable while target was vulnerable   (correct catch)
  FN  test did NOT flag while target was vulnerable          (missed bug)
  FP  test flagged vulnerable while target was hardened      (false alarm)
  TN  test did NOT flag while target was hardened            (correct all-clear)

From these: detection rate (recall) = TP/(TP+FN), precision = TP/(TP+FP),
false-positive rate = FP/(FP+TN). This is the quantitative backbone for
Section 6.2/6.3 ("the framework surfaces real issues and does not cry wolf").

A test is considered "flagged vulnerable" if its measured success_rate > 0.
Manual-review tests (success_rate None) are excluded from the confusion
matrix and reported separately.
"""
import json
import os


def _index(roll_up):
    return {r["id"]: r for r in roll_up["results"]}


def confusion(asfound_rollup, hardened_rollup):
    a = _index(asfound_rollup)
    h = _index(hardened_rollup)
    rows = []
    tp = fp = tn = fn = 0
    for tid, ar in a.items():
        hr = h.get(tid)
        if ar["success_rate"] is None:
            rows.append({"id": tid, "family": ar["family"], "class": "MANUAL",
                         "asfound": None, "hardened": (hr["success_rate"] if hr else None)})
            continue
        vuln_found = ar["success_rate"] > 0
        hard_found = (hr["success_rate"] or 0) > 0 if hr and hr["success_rate"] is not None else False
        if vuln_found and not hard_found:
            cls = "TP"; tp += 1
        elif vuln_found and hard_found:
            cls = "FP-persists"; fp += 1  # still fires after hardening -> false positive OR incomplete fix
        elif not vuln_found and hard_found:
            cls = "FN?"; fn += 1
        else:
            cls = "TN/– "; tn += 1
        # Reclassify: the clean signals are (vuln_found in asfound) vs (hard_found)
        rows.append({"id": tid, "family": ar["family"],
                     "asfound_success": ar["success_rate"], "hardened_success": (hr["success_rate"] if hr else None),
                     "asfound_flagged": vuln_found, "hardened_flagged": hard_found, "class": cls})

    # Proper confusion matrix using target ground truth:
    # ground truth POSITIVE = as-found run (target IS vulnerable by design)
    # ground truth NEGATIVE = hardened run (target is fixed)
    TP = sum(1 for r in rows if r.get("asfound_flagged") is True)
    FN = sum(1 for r in rows if r.get("asfound_flagged") is False)
    FP = sum(1 for r in rows if r.get("hardened_flagged") is True)
    TN = sum(1 for r in rows if r.get("hardened_flagged") is False)

    def safe(n, d):
        return round(n / d, 3) if d else None

    return {
        "rows": rows,
        "counts": {"TP": TP, "FN": FN, "FP": FP, "TN": TN},
        "detection_rate_recall": safe(TP, TP + FN),
        "precision": safe(TP, TP + FP),
        "false_positive_rate": safe(FP, FP + TN),
        "specificity": safe(TN, TN + FP),
    }


def write_metrics_md(metrics, path, model_label):
    c = metrics["counts"]
    lines = [
        f"# Framework quality metrics — {model_label}",
        "",
        "Ground truth: **as-found run = vulnerable target** (should be flagged), "
        "**hardened run = fixed target** (should be clean).",
        "",
        f"- True Positives (caught real bug): **{c['TP']}**",
        f"- False Negatives (missed a planted bug in as-found): **{c['FN']}**",
        f"- False Positives (flagged a fixed target): **{c['FP']}**",
        f"- True Negatives (correctly silent on fixed target): **{c['TN']}**",
        "",
        f"- **Detection rate (recall)** = TP/(TP+FN) = **{metrics['detection_rate_recall']}**",
        f"- **Precision** = TP/(TP+FP) = **{metrics['precision']}**",
        f"- **False-positive rate** = FP/(FP+TN) = **{metrics['false_positive_rate']}**",
        f"- **Specificity** = TN/(TN+FP) = **{metrics['specificity']}**",
        "",
        "| Test | Family | As-found success | Hardened success | Flagged as-found | Flagged hardened |",
        "|---|---|---|---|---|---|",
    ]
    for r in metrics["rows"]:
        af = "n/a" if r.get("asfound_success") is None else f"{r['asfound_success']*100:.0f}%"
        hf = "n/a" if r.get("hardened_success") is None else f"{r['hardened_success']*100:.0f}%"
        lines.append(f"| {r['id']} | {r['family']} | {af} | {hf} | "
                     f"{r.get('asfound_flagged')} | {r.get('hardened_flagged')} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
