#!/usr/bin/env python3
"""
Interactive AURA-Lab chat session, for manual exploration and screenshots.

Usage:
    python3 cli.py --role standard
    python3 cli.py --role admin --model mistral:7b
    python3 cli.py --role standard --context-doc DOC-008   # force T-02 doc in
    python3 cli.py --role standard --fetch-url https://intranet.auralab-corp.example/vendor-faq
"""
import argparse
import json
import config
import llm_backend
from orchestrator import AuraLabSession
from retriever import Corpus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="standard", choices=["standard", "power", "admin"])
    ap.add_argument("--backend", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--context-doc", default=None, help="Force-inject a doc id (e.g. DOC-008, DOC-010)")
    ap.add_argument("--fetch-url", default=None, help="Force-inject a fetched URL into context")
    args = ap.parse_args()

    if args.backend:
        config.BACKEND = args.backend
    backend = llm_backend.get_backend(config.BACKEND, model=args.model)
    session = AuraLabSession(role=args.role, backend=backend, corpus=Corpus())

    model_label = args.model or getattr(backend, "model", config.BACKEND)
    print(f"AURA-Lab CLI — role={args.role} backend={config.BACKEND} model={model_label} "
          f"native_tools={config.USE_NATIVE_TOOLS} strict_auth={config.STRICT_AUTH}")
    print("Type your message, or /quit to exit.\n")

    while True:
        try:
            msg = input(f"[{args.role}] > ")
        except (EOFError, KeyboardInterrupt):
            break
        if msg.strip() in ("/quit", "/exit"):
            break
        turn = session.chat(msg, extra_context_doc_id=args.context_doc,
                            fetch_url_into_context=args.fetch_url)
        print(f"\nAURA: {turn['response']}\n")
        if turn["retrieved_doc_ids"]:
            print(f"  [retrieved: {turn['retrieved_doc_ids']}]")
        if turn["tool_calls"]:
            print(f"  [tool_calls: {json.dumps(turn['tool_calls'], default=str)}]")
        print()


if __name__ == "__main__":
    main()
