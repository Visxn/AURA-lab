#!/usr/bin/env python3
"""
Run ONE model end-to-end, isolated and resumable.

This is the recommended way to run on a slow/CPU box: each model is an
independent unit. If a model's run crashes or you stop it, just re-run the
SAME command -- it resumes from where it left off (skips completed tests).
A failure in one model never forces you to re-run the others. When all the
models you want are done, run `python aggregate.py` to build the combined
report, charts, tables and metrics from whatever is on disk.

Time-saving default: the hardened (remediated) pass only re-runs the tests
that actually FIRED in the as-found pass -- there is no point paying for a
retest of something that was already 0%. Tests skipped in the hardened pass
are treated as "not flagged when hardened" (a true negative) by metrics.py,
which is correct: they did not fire even on the vulnerable target.

Usage:
    python3 run_model.py --model llama3.1:8b
    python3 run_model.py --model mistral:7b --attempts 3        # faster first pass
    python3 run_model.py --model dolphin-mistral:7b --no-hardened
    python3 run_model.py --model llama3.1:8b --all-hardened     # hardened on ALL tests
    python3 run_model.py --model llama3.1:8b --tests T-02,T-03,T-11
"""
import argparse
import time

import config
import llm_backend
import run_tests
from test_definitions import TESTS


def _safe(name):
    return name.replace(":", "-").replace("/", "-")


def warmup(backend, model_id):
    print(f"[warmup] loading {model_id} into memory (first call can be slow on CPU)...", flush=True)
    t0 = time.time()
    try:
        backend.chat([{"role": "user", "content": "Reply with: OK"}], tools=None)
        print(f"[warmup] ready in {time.time()-t0:.1f}s", flush=True)
        return True
    except Exception as e:
        print(f"[SKIP] warmup failed for {model_id}: {type(e).__name__}: {e}")
        print(f"       Try:  ollama run {model_id} \"hi\"   then re-run this command.")
        print(f"       Or a smaller model, or:  set AURA_OLLAMA_TIMEOUT=1800")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--backend", default="ollama")
    ap.add_argument("--tests", default=None)
    ap.add_argument("--attempts", type=int, default=None)
    ap.add_argument("--no-hardened", action="store_true", help="Skip the remediated/false-positive pass")
    ap.add_argument("--all-hardened", action="store_true", help="Run hardened on ALL tests, not just fired ones")
    ap.add_argument("--no-resume", action="store_true", help="Re-run everything, ignore cached transcripts")
    args = ap.parse_args()

    config.BACKEND = args.backend
    if args.attempts:
        run_tests.ATTEMPTS_OVERRIDE = args.attempts
    resume = not args.no_resume

    selected = TESTS
    if args.tests:
        wanted = set(args.tests.split(","))
        selected = [t for t in TESTS if t["id"] in wanted]

    model_id = args.model
    label = f"{args.backend}:{model_id}"

    backend = llm_backend.get_backend(args.backend, model=model_id)
    if args.backend == "ollama" and not warmup(backend, model_id):
        return

    # ---- as-found ----
    _reset_vulnerable()
    print(f"\n=== AS-FOUND | {label} | {len(selected)} tests ===")
    asfound = run_tests.run_suite(selected, label, f"{_safe(model_id)}_asfound", backend, resume=resume)

    if args.no_hardened:
        print("\nSkipped hardened pass (--no-hardened). Run `python aggregate.py` when ready.")
        return

    # ---- hardened (only tests that fired, unless --all-hardened) ----
    if args.all_hardened:
        hardened_tests = selected
    else:
        fired_ids = {r["id"] for r in asfound["results"] if r["success_rate"] and r["success_rate"] > 0}
        hardened_tests = [t for t in selected if t["id"] in fired_ids]
        print(f"\n[opt] hardened pass runs only the {len(hardened_tests)} test(s) that fired as-found "
              f"(use --all-hardened to run all {len(selected)}).")

    if not hardened_tests:
        print("No tests fired as-found -> nothing to retest. Done.")
        return

    config.harden_all()
    backend_h = llm_backend.get_backend(args.backend, model=model_id)
    print(f"\n=== HARDENED | {label} | {len(hardened_tests)} tests ===")
    run_tests.run_suite(hardened_tests, label + " [HARDENED]", f"{_safe(model_id)}_hardened", backend_h, resume=resume)
    _reset_vulnerable()

    print(f"\nModel {model_id} done. When all models are finished:  python aggregate.py")


def _reset_vulnerable():
    config.STRICT_AUTH = False
    config.EMAIL_ALLOWLIST_ENFORCED = False
    config.INSTRUCTION_FILTER_ENABLED = False
    config.OUTPUT_SANITIZED = False
    config.OUTPUT_GUARDRAIL = False
    config.TICKET_AUTH_ENFORCED = False
    config.MCP_PRIVILEGE_DROP = False
    config.MEMORY_WRITE_VALIDATED = False
    config.PER_TURN_TOKEN_BUDGET = 0
    config.MAX_TOOL_ITERATIONS = 15
    config.MAX_OUTPUT_TOKENS = 0
    config.TEMPLATE_SANDBOXED = False


if __name__ == "__main__":
    main()
