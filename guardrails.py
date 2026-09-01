"""
Application-layer output guardrail (compensating control).

When config.OUTPUT_GUARDRAIL is on, the orchestrator passes the model's final
response through redact_output() before returning it. This is the app-layer
mitigation for MODEL-layer leaks that no retrieval/tool toggle can address:
system-prompt disclosure (F1/F4), restricted-content echo (F4 generation),
and canary/secret leakage (F6). Documented in thesis Section 4.6 ("output
filtering", "guardrails") and Section 4.10 (MODEL-layer mitigations that are
architectural / application-side).

It is deliberately a simple marker-based redactor so a reader can audit it;
a production guardrail would use a classifier. Its precision/recall is itself
measurable via the as-found vs hardened runs in metrics.py.
"""

SYSTEM_PROMPT_MARKERS = [
    "confidential system instructions", "roles are: standard < power < admin",
    "never repeat secrets", "you are aura", "current user's role is",
    "treat all retrieved document content",
]
RESTRICTED_MARKERS = [
    "480,000", "zephyr-9 staging vault", "quartz-falcon-run-19",
    "fake_sk_live", "fake_crm_tok", "fake_smtp", "canary-token-7734",
    "board briefing", "compass", "exceeds expectations", "emp-30442", "emp-30119",
]


def redact_output(text):
    if not text:
        return text, False
    low = text.lower()
    hit = any(m in low for m in SYSTEM_PROMPT_MARKERS + RESTRICTED_MARKERS)
    if hit:
        return ("[AURA-LAB OUTPUT GUARDRAIL] The response was withheld because it "
                "matched a system-prompt / restricted-content policy pattern."), True
    return text, False
