#!/usr/bin/env python3
"""
Minimal Flask front-end to give F5 (Improper Output Handling) a real
rendering surface, so you can screenshot the actual XSS firing in a browser
and, with AURA_SANITIZE_OUTPUT=1, screenshot the fixed behavior for the
Phase 8 retest comparison.

Usage:
    python3 web_xss_demo.py --role standard
    open http://localhost:5000 , send the T-06 payload, observe the alert.
    AURA_SANITIZE_OUTPUT=1 python3 web_xss_demo.py   # remediated (escaped)
"""
import argparse
import config
import llm_backend
from flask import Flask, request
from orchestrator import AuraLabSession
from retriever import Corpus
from tools import render_output_sink

app = Flask(__name__)
SESSION = None

PAGE = """
<!doctype html><html><head><title>AURA-Lab (demo UI)</title></head>
<body style="font-family: sans-serif; max-width: 760px; margin: 40px auto;">
<h2>AURA-Lab — demo chat UI (F5 output-handling rig)</h2>
<p>Mode: <b>{mode}</b> (config.OUTPUT_SANITIZED={sanitized})</p>
<form method="post">
  <textarea name="msg" rows="3" style="width:100%">{last_msg}</textarea><br>
  <button type="submit">Send</button>
</form><hr>
<div id="response">{rendered}</div>
</body></html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    last_msg, rendered = "", "(no message sent yet)"
    if request.method == "POST":
        last_msg = request.form.get("msg", "")
        turn = SESSION.chat(last_msg, retrieve=False)
        rendered = render_output_sink(turn["response"])  # raw unless OUTPUT_SANITIZED
    mode = "SAFE (escaped)" if config.OUTPUT_SANITIZED else "VULNERABLE (raw HTML render)"
    return PAGE.format(mode=mode, sanitized=config.OUTPUT_SANITIZED, last_msg=last_msg, rendered=rendered)


def main():
    global SESSION
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="standard")
    ap.add_argument("--backend", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    if args.backend:
        config.BACKEND = args.backend
    backend = llm_backend.get_backend(config.BACKEND, model=args.model)
    SESSION = AuraLabSession(role=args.role, backend=backend, corpus=Corpus())
    app.run(port=args.port, debug=False)


if __name__ == "__main__":
    main()
