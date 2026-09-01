#!/usr/bin/env python3
"""
Static supply-chain review helper for T-05 (F9). Prints installed package
versions, tool/plugin permission summary, and model provenance so you have
concrete evidence to pair with the T-05 chat transcript.
"""
import json
import os
import subprocess
import sys
import config

RELEVANT = ["requests", "scikit-learn", "numpy", "pypdf", "reportlab",
            "pillow", "piexif", "flask", "matplotlib", "jinja2"]

# T-21 (F9, new): unsafe deserialization / dynamic-execution patterns. T-05
# asks the chatbot to self-report its own tool inventory -- useful, but it
# is asking the suspect for the forensic report. A real F9 review has to
# include a STATIC grep of the actual source for the classic MLSecOps red
# flags: pickle/marshal deserialization of untrusted data, eval/exec on
# model or user-controlled strings, unsafe YAML loading, and shell-out
# without argument-list execution. None of these should appear in AURA-Lab's
# own runtime path outside this review tool itself (which only greps text).
DANGEROUS_PATTERNS = [
    ("pickle.load", "unsafe deserialization (arbitrary code execution on load)"),
    ("pickle.loads", "unsafe deserialization (arbitrary code execution on load)"),
    ("yaml.load(", "unsafe YAML load without SafeLoader (arbitrary object construction)"),
    ("eval(", "dynamic evaluation of a string (code injection if the string is tainted)"),
    ("exec(", "dynamic execution of a string (code injection if the string is tainted)"),
    ("os.system(", "shell-out via string concatenation (command injection risk)"),
    ("subprocess.Popen(", "subprocess invocation -- verify shell=False and argument list, not a string"),
    ("jinja2.Template(", "unsandboxed Jinja2 rendering -- verify the input is never model/user-controlled (see T-17, TEMPLATE_SANDBOXED)"),
]
SCAN_EXCLUDE = {"supply_chain_review.py"}  # this file legitimately contains the pattern strings above


def scan_source_for_dangerous_patterns(root_dir):
    """T-21 (F9, new): static grep of every .py file under root_dir for the
    DANGEROUS_PATTERNS above. Returns a list of (file, line_no, pattern,
    reason, line_text) hits. This is intentionally a plain substring scan
    (auditable in one read, same design philosophy as detection.py) -- a
    production MLSecOps pipeline would use bandit/semgrep with real AST
    matching and lower false-positive/negative rates, but a raw grep already
    catches the textbook cases and needs zero extra dependencies."""
    hits = []
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        if os.sep + "venv" + os.sep in dirpath + os.sep or "__pycache__" in dirpath:
            continue
        for fname in filenames:
            if not fname.endswith(".py") or fname in SCAN_EXCLUDE:
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                continue
            for i, line in enumerate(lines, start=1):
                for pattern, reason in DANGEROUS_PATTERNS:
                    if pattern in line:
                        hits.append((fname, i, pattern, reason, line.strip()))
    return hits


def main():
    print("=== AURA-Lab supply-chain review (T-05 / F9) ===\n")
    print("-- Python packages in use --")
    try:
        out = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                              capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            if line.split("==")[0].lower() in RELEVANT:
                print(" ", line)
    except Exception as e:
        print("  [pip freeze failed]", e)

    print("\n-- LLM backend / model source --")
    print(f"  backend: {config.BACKEND}")
    if config.BACKEND == "ollama":
        print(f"  model: {config.OLLAMA_MODEL} (verify: `ollama show {config.OLLAMA_MODEL}`)")

    print("\n-- Tool / plugin permission review --")
    print("  TicketLookup   : ITSM read; role check", "ON" if config.TICKET_AUTH_ENFORCED else "OFF (vulnerable)")
    print("  EmailDraft     : mock send; allow-list", "ON" if config.EMAIL_ALLOWLIST_ENFORCED else "OFF (vulnerable)")
    print("  DocSummarize   : local file read; instruction filter", "ON" if config.INSTRUCTION_FILTER_ENABLED else "OFF (vulnerable)")
    print("  WebFetch       : mock external fetch; instruction filter", "ON" if config.INSTRUCTION_FILTER_ENABLED else "OFF (vulnerable)")
    print("  SqlQuery       : reporting DB; sanitization", "ON" if config.OUTPUT_SANITIZED else "OFF (vulnerable)")
    print("  RenderTemplate : Jinja2 template render; sandboxed", "ON" if config.TEMPLATE_SANDBOXED else "OFF (vulnerable, SSTI -- see T-17)")
    print("  McpAdminAction : MCP admin; privilege drop", "ON" if config.MCP_PRIVILEGE_DROP else "OFF (vulnerable)")
    print("  MemoryWrite    : persistent memory; write validation", "ON" if config.MEMORY_WRITE_VALIDATED else "OFF (vulnerable)")

    print("\n-- Corpus generated artifacts --")
    with open(config.MANIFEST_PATH) as f:
        for entry in json.load(f):
            if entry.get("generated"):
                print(f"  {entry['id']}: {entry['path']} (locally generated, not third-party sourced)")

    print("\n-- T-21: static scan for unsafe deserialization / dynamic-execution patterns --")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    hits = scan_source_for_dangerous_patterns(base_dir)
    if not hits:
        print("  [ok] no DANGEROUS_PATTERNS matches found in the harness source tree.")
    else:
        for fname, lineno, pattern, reason, line_text in hits:
            print(f"  [FLAG] {fname}:{lineno}  pattern='{pattern}'  -- {reason}")
            print(f"         {line_text}")
        print(f"\n  {len(hits)} pattern hit(s). Triage each: confirm whether the input reaching that")
        print("  call site can ever be model- or user-controlled before treating it as a finding.")

    print("\nComplete the T-05 finding with this output + the chat transcript.")
    print("Complete the T-21 finding with the static-scan output above (F9, automated half of supply-chain review).")


if __name__ == "__main__":
    main()
