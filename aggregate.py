#!/usr/bin/env python3
"""
Aggregate whatever per-model evidence is already on disk into the combined
report, charts, tables and metrics -- WITHOUT re-running any model.

Scans evidence/ for '<model>_asfound/results.json' (and optional
'<model>_hardened/results.json'), pairs them per model, rebuilds matrix.json,
computes per-model framework metrics, and regenerates:
    evidence/report.html, evidence/charts/*.png,
    evidence/tables/*.md, evidence/<model>_metrics.md

Run this after finishing one or more `python run_model.py --model X` runs.
Re-runnable any time; it just reflects the current state of evidence/.

Usage:
    python3 aggregate.py
    python3 aggregate.py --models llama3.1:8b,mistral:7b   # restrict/order
"""
import argparse
import json
import os

import config
import models as model_registry
import metrics as metrics_mod
import report_generator
import charts


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def discover_models():
    ev = config.EVIDENCE_DIR
    found = {}
    if not os.path.isdir(ev):
        return found
    for name in os.listdir(ev):
        full = os.path.join(ev, name)
        if not os.path.isdir(full):
            continue
        if name.endswith("_asfound"):
            found.setdefault(name[:-len("_asfound")], {})["asfound"] = full
        elif name.endswith("_hardened"):
            found.setdefault(name[:-len("_hardened")], {})["hardened"] = full
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=None, help="Comma-separated safe model dirs to include/order")
    args = ap.parse_args()

    found = discover_models()
    if not found:
        print(f"No per-model evidence found under {config.EVIDENCE_DIR}/. "
              f"Run `python run_model.py --model <id>` first.")
        return

    order = args.models.split(",") if args.models else None
    keys = [k.replace(":", "-").replace("/", "-") for k in order] if order else sorted(found)

    matrix = {"models": [], "generated": None}
    for safe_key in keys:
        entry = found.get(safe_key)
        if not entry or "asfound" not in entry:
            print(f"[skip] {safe_key}: no as-found results")
            continue
        asfound = _load(os.path.join(entry["asfound"], "results.json"))
        # model_label is "<backend>:<model_id>", e.g. "ollama:dolphin-mistral:7b".
        # split(":", 1) peels off only the backend prefix; an unbounded split
        # on ":" collapsed both "mistral:7b" and "dolphin-mistral:7b" to the
        # same "7b" tag, silently colliding their registry lookup and their
        # table8/table9 output files.
        model_id = asfound.get("model_label", safe_key).split(":", 1)[-1].replace(" [HARDENED]", "")
        meta = model_registry.get(model_id)
        hardened = None
        model_metrics = None
        if "hardened" in entry and os.path.exists(os.path.join(entry["hardened"], "results.json")):
            hardened = _load(os.path.join(entry["hardened"], "results.json"))
            model_metrics = metrics_mod.confusion(asfound, hardened)
            metrics_mod.write_metrics_md(
                model_metrics, os.path.join(config.EVIDENCE_DIR, f"{safe_key}_metrics.md"),
                asfound.get("model_label", model_id))
        matrix["models"].append({
            "model_id": model_id, "guardrail": meta["guardrail"], "backend": meta["backend"],
            "notes": meta.get("notes", ""), "asfound": asfound,
            "hardened": hardened, "metrics": model_metrics,
        })
        print(f"[ok] aggregated {model_id} "
              f"(as-found + {'hardened' if hardened else 'no hardened'})")

    if not matrix["models"]:
        print("Nothing to aggregate.")
        return

    from run_tests import _now
    matrix["generated"] = _now()
    with open(os.path.join(config.EVIDENCE_DIR, "matrix.json"), "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=2, default=str)

    charts.generate_all(matrix)
    report_generator.generate_all(matrix)
    print(f"\nDone. {len(matrix['models'])} model(s) aggregated.")
    print("  -> evidence/report.html")
    print("  -> evidence/tables/*.md")
    print("  -> evidence/charts/*.png")
    print("  -> evidence/<model>_metrics.md")


if __name__ == "__main__":
    main()
