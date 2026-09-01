#!/usr/bin/env python3
"""
Multi-model comparison runner (thesis Section 6.2 external validity).

For each model in the comparison set, runs the FULL suite twice:
  - as-found  (target vulnerable)   -> true positives
  - hardened  (all fixes ON)        -> false-positive check
then computes per-model framework metrics and a cross-model comparison, and
finally invokes the report + chart generators.

Usage:
    python3 run_matrix.py                                  # DEFAULT_COMPARISON models
    python3 run_matrix.py --models llama3.1:8b,mistral:7b
    python3 run_matrix.py --backend stub                   # dry-run plumbing (single fake model)
    python3 run_matrix.py --no-hardened                    # skip the false-positive pass (faster)
    python3 run_matrix.py --tests T-01,T-02,T-03           # subset

Every model's guardrail level is recorded (models.py) and stamped into the
report, so using a weakly-aligned model is always disclosed, never hidden.
"""
import argparse
import json
import os

import config
import llm_backend
import models as model_registry
import metrics as metrics_mod
from test_definitions import TESTS
from run_tests import run_suite


def _safe(name):
    return name.replace(":", "-").replace("/", "-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=None, help="Comma-separated model ids (default: models.DEFAULT_COMPARISON)")
    ap.add_argument("--backend", default=None, help="Force a backend (e.g. stub) for ALL models")
    ap.add_argument("--tests", default=None)
    ap.add_argument("--no-hardened", action="store_true", help="Skip the hardened false-positive pass")
    ap.add_argument("--no-report", action="store_true", help="Skip report/chart generation")
    args = ap.parse_args()

    selected = TESTS
    if args.tests:
        wanted = set(args.tests.split(","))
        selected = [t for t in TESTS if t["id"] in wanted]

    if args.backend == "stub":
        model_ids = ["stub-weak"]
    else:
        model_ids = args.models.split(",") if args.models else model_registry.DEFAULT_COMPARISON

    matrix = {"models": [], "generated": None}
    os.makedirs(config.EVIDENCE_DIR, exist_ok=True)

    for model_id in model_ids:
        meta = model_registry.get(model_id)
        backend_name = args.backend or meta["backend"]
        guardrail = meta["guardrail"] if not args.backend == "stub" else "weak(stub)"
        print(f"\n########## MODEL {model_id} (guardrail={guardrail}, backend={backend_name}) ##########")

        # --- as-found run ---
        # reset config toggles to vulnerable defaults for each model
        _reset_vulnerable()
        backend = llm_backend.get_backend(backend_name, model=None if args.backend == "stub" else model_id)
        label = f"{backend_name}:{model_id}"

        # warmup / preflight: one bounded call so a cold-load or unreachable
        # model fails HERE with a clear message, not 20 tests deep.
        if backend_name == "ollama":
            import time
            print(f"  [warmup] loading {model_id} into memory (first call can be slow)...", flush=True)
            try:
                t0 = time.time()
                backend.chat([{"role": "user", "content": "Reply with: OK"}], tools=None)
                print(f"  [warmup] ready in {time.time()-t0:.1f}s", flush=True)
            except Exception as e:
                print(f"  [SKIP] {model_id}: warmup failed ({type(e).__name__}: {e}).")
                print(f"         Try: ollama run {model_id} \"hi\"  (pre-warm), or a smaller model,")
                print(f"         or raise AURA_OLLAMA_TIMEOUT. Skipping this model.\n")
                continue

        asfound = run_suite(selected, label, f"{_safe(model_id)}_asfound", backend)

        hardened = None
        model_metrics = None
        if not args.no_hardened:
            config.harden_all()
            backend_h = llm_backend.get_backend(backend_name, model=None if args.backend == "stub" else model_id)
            hardened = run_suite(selected, label + " [HARDENED]", f"{_safe(model_id)}_hardened", backend_h)
            model_metrics = metrics_mod.confusion(asfound, hardened)
            metrics_mod.write_metrics_md(
                model_metrics, os.path.join(config.EVIDENCE_DIR, f"{_safe(model_id)}_metrics.md"), label)
            _reset_vulnerable()

        matrix["models"].append({
            "model_id": model_id, "guardrail": guardrail, "backend": backend_name,
            "notes": meta.get("notes", ""), "asfound": asfound,
            "hardened": hardened, "metrics": model_metrics,
        })

    from run_tests import _now
    matrix["generated"] = _now()
    matrix_path = os.path.join(config.EVIDENCE_DIR, "matrix.json")
    with open(matrix_path, "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=2, default=str)
    print(f"\nMatrix saved to {matrix_path}")

    if not args.no_report:
        # charts FIRST so the HTML report can embed them
        try:
            import charts
            charts.generate_all(matrix)
            print("Charts generated: evidence/charts/*.png")
        except Exception as e:
            print(f"[warn] chart generation failed: {e}")
        try:
            import report_generator
            report_generator.generate_all(matrix)
            print("Report generated: evidence/report.html + evidence/tables/*.md")
        except Exception as e:
            print(f"[warn] report generation failed: {e}")


def _reset_vulnerable():
    """Force every toggle back to its vulnerable default between runs."""
    config.STRICT_AUTH = False
    config.EMAIL_ALLOWLIST_ENFORCED = False
    config.INSTRUCTION_FILTER_ENABLED = False
    config.OUTPUT_SANITIZED = False
    config.TICKET_AUTH_ENFORCED = False
    config.MCP_PRIVILEGE_DROP = False
    config.MEMORY_WRITE_VALIDATED = False
    config.OUTPUT_GUARDRAIL = False
    config.PER_TURN_TOKEN_BUDGET = 0
    config.MAX_TOOL_ITERATIONS = 15
    config.MAX_OUTPUT_TOKENS = 0
    config.TEMPLATE_SANDBOXED = False


if __name__ == "__main__":
    main()
