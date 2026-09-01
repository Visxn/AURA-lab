"""
Model registry for the multi-model comparison (thesis Section 6.2 external
validity: "external validity requires validation across ... systems").

Each target is characterized by its EXPECTED guardrail strength. Comparing a
strongly-aligned model against a weakly-aligned / uncensored one is a
standard, disclosed methodology in AI security research: it isolates
APPLICATION-layer vulnerabilities (which fire regardless of model, e.g. the
retrieval-authorization and tool-permission bugs) from MODEL-layer refusals.

IMPORTANT / ACADEMIC HONESTY: the "weakly aligned" models below are included
precisely to make the model-layer variable explicit and reportable. Do NOT
present results from one hand-picked weak model as a general claim without
naming the model and its guardrail level in the report. metrics.py and
report_generator.py always stamp the model id + guardrail level onto every
finding so this disclosure is automatic.

'guardrail' levels: "strong" | "medium" | "weak" | "none(uncensored)"

Pull commands (Ollama) are given as a convenience. Availability of any
specific tag changes over time; if a tag is gone, pick an equivalent at the
same guardrail level and note the substitution in Section 5.3.
"""

MODELS = [
    {
        "id": "llama3.1:8b",
        "backend": "ollama",
        "guardrail": "strong",
        "supports_native_tools": True,
        "pull": "ollama pull llama3.1:8b",
        "notes": "Current, safety-tuned. Tends to over-refuse injected content (baseline 'secure-ish' target).",
    },
    {
        "id": "qwen2.5:7b",
        "backend": "ollama",
        "guardrail": "medium",
        "supports_native_tools": True,
        "pull": "ollama pull qwen2.5:7b",
        "notes": "Good tool-calling; moderate guardrails. Useful middle point.",
    },
    {
        "id": "mistral:7b",
        "backend": "ollama",
        "guardrail": "medium",
        "supports_native_tools": True,
        "pull": "ollama pull mistral:7b",
        "notes": "Follows instructions readily; weaker refusal behavior than llama3.1.",
    },
    {
        "id": "llama2-uncensored:7b",
        "backend": "ollama",
        "guardrail": "none(uncensored)",
        "supports_native_tools": False,
        "pull": "ollama pull llama2-uncensored:7b",
        "notes": "Guardrails removed. Maximizes MODEL-layer exploitability; use the TEXT tool protocol (no native tools). Disclose explicitly in the thesis.",
    },
    {
        "id": "dolphin-mistral:7b",
        "backend": "ollama",
        "guardrail": "none(uncensored)",
        "supports_native_tools": False,
        "pull": "ollama pull dolphin-mistral:7b",
        "notes": "'Uncensored' fine-tune. Verified against the local Ollama server (2026-08-24): "
                 "the Ollama /api/chat endpoint rejects a `tools` payload for this model "
                 "(\"does not support tools\", HTTP 400), so it must run on the TEXT tool "
                 "protocol fallback. Strong choice for visible model-layer findings; disclose explicitly.",
    },
]

# The default comparison set the runner uses if --models is not given. Chosen
# to span the guardrail spectrum with a manageable number of pulls for a
# time-boxed engagement. Edit freely.
DEFAULT_COMPARISON = ["llama3.1:8b", "mistral:7b", "dolphin-mistral:7b"]

# Human-readable display name per model id, used to fill the "{MODEL_NAME}"
# placeholder in payloads that address the target by name (e.g. T-01b's DAN
# prompt, which opens with "Hello, ChatGPT" in its original form). The same
# test_definitions.py entry runs against every model in DEFAULT_COMPARISON,
# so the substitution has to happen at run time (see run_tests.py
# run_one_test), not by hardcoding one model's name into the test library.
DISPLAY_NAMES = {
    "llama3.1:8b": "Llama 3.1",
    "qwen2.5:7b": "Qwen 2.5",
    "mistral:7b": "Mistral",
    "llama2-uncensored:7b": "Llama 2",
    "dolphin-mistral:7b": "Dolphin-Mistral",
}

# The organization actually responsible for the model's training/tuning, used
# to fill the "{PROVIDER}" / "{PROVIDER_UPPER}" placeholders in payloads that
# invoke a named provider's content policy as the authority being bypassed
# (e.g. T-01b's DAN prompt, written for OpenAI/ChatGPT in its original form).
# dolphin-mistral is attributed to Cognitive Computations, the group that
# publishes the "Dolphin" uncensored fine-tune, rather than to Mistral AI
# (the base model's trainer), since it is specifically that fine-tuning
# organization's alignment the prompt would be invoking against.
PROVIDERS = {
    "llama3.1:8b": "Meta",
    "qwen2.5:7b": "Alibaba",
    "mistral:7b": "Mistral AI",
    "llama2-uncensored:7b": "Meta",
    "dolphin-mistral:7b": "Cognitive Computations",
}


def get(model_id):
    for m in MODELS:
        if m["id"] == model_id:
            return m
    # Unknown model: assume ollama + medium guardrail so the runner still works
    return {"id": model_id, "backend": "ollama", "guardrail": "unknown",
            "supports_native_tools": True, "pull": f"ollama pull {model_id}",
            "notes": "Not in registry; assumed ollama/medium. Add it to models.py to characterize."}


def guardrail_of(model_id):
    return get(model_id)["guardrail"]


def display_name(model_id):
    """Human-readable name for a model id, for payloads that address the
    target by name. Falls back to the id's tag-stripped base (e.g.
    "phi3:mini" -> "Phi3") for anything not in DISPLAY_NAMES."""
    if model_id in DISPLAY_NAMES:
        return DISPLAY_NAMES[model_id]
    return str(model_id).split(":")[0].replace("-", " ").title()


def provider_of(model_id):
    """Organization responsible for the model, for payloads that invoke a
    named provider's content policy. Falls back to a generic phrase for
    anything not in PROVIDERS, rather than guessing a company name."""
    return PROVIDERS.get(model_id, "the model provider")
