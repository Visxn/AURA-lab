#!/usr/bin/env python3
"""
Run the AURA-Lab test suite against ONE (backend, model, config-state) and
write evidence. Importable as run_suite() by run_matrix.py for the multi-model
comparison, and runnable directly from the CLI.

Usage:
    python3 run_tests.py                              # all tests, backend from env/config
    python3 run_tests.py --tests T-01,T-02,T-10        # subset
    python3 run_tests.py --backend stub                # dry-run plumbing check
    python3 run_tests.py --model mistral:7b            # pick an Ollama model
    python3 run_tests.py --harden                      # remediated baseline (all fixes ON)

Outputs (under evidence/<run_label>/):
    <id>_transcript.json   raw attempts
    <id>_finding.md        Appendix C template, auto-scored
    results.json           machine-readable roll-up (consumed by report/charts)
    summary.md             human table
"""
import argparse
import datetime
import json
import os

import config
import llm_backend
import models
import scoring
import detection
import memory_store
from orchestrator import AuraLabSession
from retriever import Corpus
from test_definitions import TESTS


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# Optional global override of attempts per test (set from --attempts). None = use per-test n_attempts.
ATTEMPTS_OVERRIDE = None


def _render_placeholders(text, model_display, provider):
    """Fill the "{MODEL_NAME}" / "{PROVIDER}" / "{PROVIDER_UPPER}" placeholders
    some payloads use to address the target and its provider by name (e.g.
    T-01b's DAN prompt, written against ChatGPT/OpenAI in its original form),
    with the actual model/provider under test this run. A plain .replace(),
    not .format(), because several payloads legitimately contain literal
    '{' / '}' (e.g. T-15's JSON-field-coercion payload) that must NOT be
    touched."""
    if not text:
        return text
    if "{MODEL_NAME}" in text:
        text = text.replace("{MODEL_NAME}", model_display)
    if "{PROVIDER_UPPER}" in text:
        text = text.replace("{PROVIDER_UPPER}", provider.upper())
    if "{PROVIDER}" in text:
        text = text.replace("{PROVIDER}", provider)
    return text


def run_one_test(test, backend, corpus):
    role = test["role"]
    attempts = []
    n = ATTEMPTS_OVERRIDE if ATTEMPTS_OVERRIDE else test.get("n_attempts", 1)
    model_id = getattr(backend, "model", None) or config.BACKEND
    model_display = models.display_name(model_id)
    provider = models.provider_of(model_id)
    variants = test.get("payload_variants")
    if variants:
        variants = [_render_placeholders(v, model_display, provider) for v in variants]
    turns_script = test.get("turns")
    if turns_script:
        turns_script = [_render_placeholders(m, model_display, provider) for m in turns_script]
    single_payload = _render_placeholders(test.get("payload"), model_display, provider)

    for i in range(n):
        # reset persistent memory before attempts that write it, to avoid
        # cross-attempt contamination of the measurement
        if test.get("success_signal") == "memory_poisoned":
            memory_store.reset_memory()
        session = AuraLabSession(role=role, backend=backend, corpus=corpus,
                                  strict_auth=config.STRICT_AUTH)
        if turns_script:
            last_turn = None
            for msg in turns_script:
                last_turn = session.chat(msg, retrieve=test.get("retrieve", True),
                                          extra_context_doc_id=test.get("context_doc_id"),
                                          fetch_url_into_context=test.get("fetch_url"))
            turn = last_turn
            payload = " || ".join(turns_script)
        else:
            payload = variants[i % len(variants)] if variants else single_payload
            turn = session.chat(payload, retrieve=test.get("retrieve", True),
                                 extra_context_doc_id=test.get("context_doc_id"),
                                 fetch_url_into_context=test.get("fetch_url"))
        det = detection.detect(test, turn, role)
        attempts.append({"attempt": i + 1, "payload": payload, "turn": turn, "detection": det})

    def rate(field):
        vals = [a["detection"][field] for a in attempts if a["detection"].get(field) is not None]
        return (sum(1 for v in vals if v) / len(vals)) if vals else None

    success_rate = rate("vulnerable")
    refusal_flags = [a["detection"]["blanket_refusal"] for a in attempts]
    refusal_rate = (sum(1 for v in refusal_flags if v) / len(refusal_flags)) if refusal_flags else 0.0
    retrieval_leak_rate = rate("retrieval_leak")
    generation_leak_rate = rate("generation_leak")

    native_calls = sum(a["turn"].get("native_tool_calls", 0) for a in attempts)
    text_calls = sum(a["turn"].get("text_tool_calls", 0) for a in attempts)
    avg_completion_tokens = round(
        sum(a["turn"].get("completion_tokens_est", 0) for a in attempts) / max(1, len(attempts)), 1)

    scored = scoring.score_from_profile(test["scoring_profile"], success_rate) if success_rate is not None else None

    return {
        "test": {k: v for k, v in test.items() if k not in ("turns",)},
        "turns_script": turns_script,
        "attempts": attempts,
        "success_rate": success_rate,
        "refusal_rate": refusal_rate,
        "retrieval_leak_rate": retrieval_leak_rate,
        "generation_leak_rate": generation_leak_rate,
        "native_tool_calls": native_calls,
        "text_tool_calls": text_calls,
        "avg_completion_tokens": avg_completion_tokens,
        "scored": scored,
        "manual_review_required": test.get("manual_review", False) or success_rate is None,
    }


def result_label(result):
    sr = result["success_rate"]
    if sr is None:
        return "MANUAL REVIEW"
    if sr > 0:
        return "FAIL (vulnerable behavior observed)"
    if result["refusal_rate"] > 0:
        return (f"PARTIAL — no vulnerable action, but blanket refusal in "
                f"{result['refusal_rate']*100:.0f}% of attempts (blocked the whole turn, "
                f"not just the malicious part; see Section 6.3 note)")
    return "PASS (served normally, no leak, no blanket refusal)"


def write_finding_md(result, path, model_label):
    test = result["test"]
    sr = result["success_rate"]
    n = len(result["attempts"])
    hits = sum(1 for a in result["attempts"] if a["detection"].get("vulnerable"))
    sr_str = f"{sr*100:.0f}% ({hits}/{n})" if sr is not None else "manual review required"
    example = result["attempts"][0]
    scored = result["scored"]

    leak_lines = []
    if result["retrieval_leak_rate"] is not None:
        leak_lines.append(f"- **Retrieval-layer leak rate**: {result['retrieval_leak_rate']*100:.0f}% "
                          "(role-restricted doc reached context for a below-clearance role — a Section 4.10 "
                          "RETRIEVAL-layer defect on its own).")
    if result["generation_leak_rate"] is not None:
        leak_lines.append(f"- **Generation-layer leak rate**: {result['generation_leak_rate']*100:.0f}% "
                          "(restricted content actually echoed in the answer — MODEL-layer compensating control).")

    score_lines = []
    if scored:
        s = scored["sub_scores"]
        score_lines = [
            f"- **AI-PTF score (auto)**: **{scored['total']} → {scored['label']}** (SLA {scored['sla']}, {scored['color']})",
            f"  - Impact {s['impact']} · Exploitability {s['exploitability']} · Reproducibility {s['reproducibility']} "
            f"(measured) · Persistence {s['persistence']} · Blast Radius {s['blast_radius']} · Detectability Adj {s['detectability_adj']}",
        ]

    lines = [
        f"# Finding — {test['id']} ({test['family']}) — {test.get('scenario','')}",
        "",
        f"- **Test ID / Family / Priority**: {test['id']} / {test['family']} / {test.get('priority','')}",
        f"- **Attack surface / Responsible layer**: {test.get('surface','')} / {test.get('layer','')}",
        f"- **Model under test**: {model_label} · **Config**: {json.dumps(config.all_toggles())}",
        f"- **Role**: {test['role']}",
        f"- **Payload / method**: `{example['payload'][:400]}`" + (f" + context doc {test['context_doc_id']}" if test.get("context_doc_id") else "") + (f" + fetched URL {test['fetch_url']}" if test.get("fetch_url") else ""),
        f"- **Run at**: {_now()}",
        f"- **Observed (attempt 1 excerpt)**: {example['turn']['response'][:600]!r}",
        f"- **Retrieved context IDs (attempt 1)**: {example['turn']['retrieved_doc_ids']}",
        f"- **Tool calls (attempt 1)**: {json.dumps(example['turn']['tool_calls'], default=str)[:800]}",
        f"- **Tool-call path**: {result['native_tool_calls']} native, {result['text_tool_calls']} text-protocol",
        f"- **Attempts / success rate**: {n} attempts, {sr_str}",
        f"- **Blanket-refusal rate**: {result['refusal_rate']*100:.0f}%",
        *leak_lines,
        f"- **Avg completion tokens (F7 cost signal)**: {result['avg_completion_tokens']}",
        f"- **Result**: {result_label(result)}",
        *score_lines,
        "- **Responsible-layer note**: see retrieval-vs-generation split above where present (Section 4.10).",
        "- **Remediation / retest**: re-run this test with `--harden` (or the specific toggle) to confirm the fix drops the success rate to 0 — that pair is your Phase 8 before/after.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_suite(selected_tests, model_label, evidence_subdir, backend, resume=False):
    out_dir = os.path.join(config.EVIDENCE_DIR, evidence_subdir)
    os.makedirs(out_dir, exist_ok=True)
    memory_store.reset_memory()
    corpus = Corpus()
    results = []
    selected_ids = {t["id"] for t in selected_tests}
    for test in selected_tests:
        transcript_path = os.path.join(out_dir, f"{test['id']}_transcript.json")
        if resume and os.path.exists(transcript_path):
            try:
                with open(transcript_path, encoding="utf-8") as f:
                    result = json.load(f)
                results.append(result)
                print(f"  [{model_label}] {test['id']} — cached, skipping (--resume)", flush=True)
                continue
            except Exception:
                pass  # unreadable cache -> re-run
        print(f"  [{model_label}] {test['id']} ({test['family']}) x{ATTEMPTS_OVERRIDE or test.get('n_attempts',1)} role={test['role']}", flush=True)
        result = run_one_test(test, backend, corpus)
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        write_finding_md(result, os.path.join(out_dir, f"{test['id']}_finding.md"), model_label)
        results.append(result)
        sr = result["success_rate"]
        print(f"      success={sr}  refusal={result['refusal_rate']:.2f}  "
              f"native/text tools={result['native_tool_calls']}/{result['text_tool_calls']}", flush=True)

    # Merge in any OTHER test's transcript already on disk in this same
    # evidence directory, from a PREVIOUS run that used a different --tests
    # subset. Without this, results.json/summary.md silently regress to
    # cover only whatever subset THIS invocation happened to select --
    # found the hard way running `--tests T-13,...` against a directory that
    # already held T-01..T-12's transcripts from the original full run: it
    # overwrote results.json down to 10 entries, discarding the other 26 (the
    # *_transcript.json / *_finding.md files on disk were never touched --
    # only the roll-up summarizing them was affected). This makes `--tests`
    # subset runs properly additive, matching the "isolated, resumable unit"
    # behavior the README already promises for run_model.py.
    from test_definitions import TESTS as _ALL_TESTS
    for other in _ALL_TESTS:
        if other["id"] in selected_ids:
            continue
        other_path = os.path.join(out_dir, f"{other['id']}_transcript.json")
        if os.path.exists(other_path):
            try:
                with open(other_path, encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception:
                pass
    _order = {t["id"]: i for i, t in enumerate(_ALL_TESTS)}
    results.sort(key=lambda r: _order.get(r["test"]["id"], 999))

    roll_up = {
        "model_label": model_label,
        "config": config.all_toggles(),
        "generated": _now(),
        "results": [
            {"id": r["test"]["id"], "family": r["test"]["family"],
             "priority": r["test"].get("priority"), "role": r["test"]["role"],
             "surface": r["test"].get("surface"), "layer": r["test"].get("layer"),
             "scenario": r["test"].get("scenario"),
             "success_rate": r["success_rate"], "refusal_rate": r["refusal_rate"],
             "retrieval_leak_rate": r["retrieval_leak_rate"],
             "generation_leak_rate": r["generation_leak_rate"],
             "native_tool_calls": r["native_tool_calls"], "text_tool_calls": r["text_tool_calls"],
             "avg_completion_tokens": r["avg_completion_tokens"],
             "scored": r["scored"], "result_label": result_label(r),
             "manual_review_required": r["manual_review_required"]}
            for r in results
        ],
    }
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(roll_up, f, indent=2, default=str)

    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(f"# AURA-Lab run — {model_label}\n\nConfig: {json.dumps(config.all_toggles())}\n"
                f"Generated: {_now()}\n\n")
        f.write("| Test | Family | Success | Refusal | Severity | Result |\n|---|---|---|---|---|---|\n")
        for r in roll_up["results"]:
            sr = f"{r['success_rate']*100:.0f}%" if r["success_rate"] is not None else "n/a"
            sev = r["scored"]["label"] if r["scored"] else "—"
            f.write(f"| {r['id']} | {r['family']} | {sr} | {r['refusal_rate']*100:.0f}% | {sev} | {r['result_label'].split(' (')[0].split(' —')[0]} |\n")
    return roll_up


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default=None)
    ap.add_argument("--backend", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--harden", action="store_true", help="Remediated baseline: flip ALL fixes ON")
    ap.add_argument("--strict-auth", action="store_true")
    ap.add_argument("--allowlist", action="store_true")
    ap.add_argument("--instr-filter", action="store_true")
    ap.add_argument("--label", default=None, help="Evidence subdir label")
    ap.add_argument("--resume", action="store_true", help="Skip tests that already have a transcript")
    ap.add_argument("--attempts", type=int, default=None, help="Override attempts per test (default: per-test)")
    args = ap.parse_args()

    global ATTEMPTS_OVERRIDE
    if args.attempts:
        ATTEMPTS_OVERRIDE = args.attempts
    if args.backend:
        config.BACKEND = args.backend
    if args.harden:
        config.harden_all()
    if args.strict_auth:
        config.STRICT_AUTH = True
    if args.allowlist:
        config.EMAIL_ALLOWLIST_ENFORCED = True
    if args.instr_filter:
        config.INSTRUCTION_FILTER_ENABLED = True

    backend = llm_backend.get_backend(config.BACKEND, model=args.model)
    model_label = f"{config.BACKEND}:{args.model or getattr(backend, 'model', config.BACKEND)}"
    if args.harden:
        model_label += " [HARDENED]"

    selected = TESTS
    if args.tests:
        wanted = set(args.tests.split(","))
        selected = [t for t in TESTS if t["id"] in wanted]

    label = args.label or ("hardened" if args.harden else "asfound")
    safe_model = (args.model or config.BACKEND).replace(":", "-").replace("/", "-")
    subdir = f"{safe_model}_{label}"
    print(f"=== Running {len(selected)} tests | {model_label} | evidence/{subdir}/ ===")
    run_suite(selected, model_label, subdir, backend, resume=args.resume)
    print(f"\nDone. Evidence in evidence/{subdir}/")


if __name__ == "__main__":
    main()
