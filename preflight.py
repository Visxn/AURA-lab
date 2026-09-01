#!/usr/bin/env python3
"""
Preflight check: run this BEFORE the suite to confirm your Ollama setup is
healthy and to measure how fast (or slow) a single model call is on your
machine. It catches the two common Windows/CPU problems early:

  1. Cold start   -> first call loads the model into RAM (can take minutes).
  2. Slow CPU     -> each generation is slow; pick a smaller model.

Usage:
    python3 preflight.py                       # checks config.OLLAMA_MODEL
    python3 preflight.py --model llama3.2:3b    # check a specific model
    python3 preflight.py --models llama3.1:8b,mistral:7b,dolphin-mistral:7b
"""
import argparse
import time
import requests
import config
import llm_backend


def check_server():
    try:
        r = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=10)
        r.raise_for_status()
        tags = [m["name"] for m in r.json().get("models", [])]
        print(f"[ok] Ollama reachable at {config.OLLAMA_HOST}")
        print(f"     installed models: {tags if tags else '(none pulled yet!)'}")
        return tags
    except Exception as e:
        print(f"[FAIL] Cannot reach Ollama at {config.OLLAMA_HOST}: {e}")
        print("       -> Is `ollama serve` running? Is the port 11434?")
        return None


def time_one_call(model):
    print(f"\n--- Timing one call to '{model}' (this also warms it into RAM) ---")
    backend = llm_backend.get_backend("ollama", model=model)
    t0 = time.time()
    try:
        env = backend.chat(
            [{"role": "system", "content": "You are a test."},
             {"role": "user", "content": "Reply with the single word: OK"}],
            tools=None)
        dt = time.time() - t0
        print(f"[ok] responded in {dt:.1f}s  | text={env['text'][:60]!r}  native_support={backend.supports_native}")
        if dt > 60:
            print("     NOTE: >60s per call. The full suite (~26 tests x 5 attempts x 2 configs")
            print("     x N models) will be very long. Consider a smaller model (llama3.2:3b,")
            print("     qwen2.5:3b) or run subsets with --tests.")
        return dt
    except requests.exceptions.ReadTimeout:
        print(f"[FAIL] Timed out after {config.OLLAMA_TIMEOUT}s.")
        print("       -> First load of a big model on CPU can exceed this. Try:")
        print(f"          1) Pre-warm once in a terminal:  ollama run {model} \"hi\"")
        print("          2) Use a smaller model:           --model llama3.2:3b")
        print("          3) Raise the timeout:  set AURA_OLLAMA_TIMEOUT=1800  (Windows)")
        return None
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--models", default=None)
    args = ap.parse_args()

    tags = check_server()
    models = []
    if args.models:
        models = args.models.split(",")
    elif args.model:
        models = [args.model]
    else:
        models = [config.OLLAMA_MODEL]

    if tags is not None:
        for m in models:
            base = m.split(":")[0]
            if not any(t == m or t.startswith(base) for t in tags):
                print(f"\n[warn] '{m}' not found in installed models. Pull it: ollama pull {m}")
                continue
            time_one_call(m)

    print("\nPreflight done. If a model responded in a reasonable time, run:")
    print("   python run_matrix.py --models " + ",".join(models))


if __name__ == "__main__":
    main()
