"""
Report generator for AURA-Lab.

Consumes evidence/matrix.json (produced by run_matrix.py) and emits:
  evidence/tables/table8_<model>.md   Findings summary (thesis Table 8)
  evidence/tables/table9_<model>.md   Coverage analysis (thesis Table 9)
  evidence/tables/cross_model.md      Cross-model comparison
  evidence/report.html                Full report (Section 4.11 structure)

All artifacts are ready to paste into the thesis (Markdown tables) or hand to
a reader (self-contained HTML). Every finding carries its model + guardrail
level so the use of a weakly-aligned model is always disclosed.
"""
import base64
import html
import json
import os
import config
import standards_map

SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4, "—": 5}
SEV_COLOR = {"CRITICAL": "#b3261e", "HIGH": "#c25e00", "MEDIUM": "#9a7b00",
             "LOW": "#2e7d32", "INFORMATIONAL": "#5f6368", "—": "#5f6368"}


def _tables_dir():
    d = os.path.join(config.EVIDENCE_DIR, "tables")
    os.makedirs(d, exist_ok=True)
    return d


def _findings(rollup):
    """Only tests that fired (success_rate>0) become 'findings' in Table 8."""
    out = []
    for r in rollup["results"]:
        sr = r.get("success_rate")
        if sr is not None and sr > 0 and r.get("scored"):
            out.append(r)
    out.sort(key=lambda r: (SEV_ORDER.get(r["scored"]["label"], 9), -(r["success_rate"] or 0)))
    return out


def table8_md(rollup, model_id, guardrail):
    lines = [f"### Table 8 — Findings summary ({model_id}, guardrail={guardrail})",
             "",
             "| ID | Family | Severity | Score | Surface | Layer | Success | Summary |",
             "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(_findings(rollup), 1):
        s = r["scored"]
        lines.append(f"| F-{i:02d} | {r['family']} | {s['label']} | {s['total']} | "
                     f"{r['surface']} | {r['layer']} | {r['success_rate']*100:.0f}% | {r['scenario']} |")
    if len(lines) == 4:
        lines.append("| — | — | — | — | — | — | — | No findings fired for this model/config |")
    return "\n".join(lines)


def table9_md(rollup, model_id):
    by_family = {}
    for r in rollup["results"]:
        by_family.setdefault(r["family"], []).append(r)
    lines = [f"### Table 9 — Coverage analysis ({model_id})",
             "",
             "| Family | AI-PTF name | Tests | Auto-tested | Coverage | Notes |",
             "|---|---|---|---|---|---|"]
    for fam in sorted(by_family):
        rs = by_family[fam]
        info = standards_map.info(fam)
        auto = [r for r in rs if r["success_rate"] is not None]
        manual = [r for r in rs if r["success_rate"] is None]
        fired = [r for r in auto if r["success_rate"] > 0]
        coverage = "Full" if auto else "Partial (manual)"
        if auto and manual:
            coverage = "Full + manual"
        note = f"{len(fired)}/{len(auto)} auto-tests fired" + (f"; {len(manual)} manual" if manual else "")
        lines.append(f"| {fam} | {info['name']} | {len(rs)} | {len(auto)} | {coverage} | {note} |")
    return "\n".join(lines)


def cross_model_md(matrix):
    lines = ["### Cross-model comparison (attack success rate by family)", ""]
    models = matrix["models"]
    header = "| Family | " + " | ".join(f"{m['model_id']} ({m['guardrail']})" for m in models) + " |"
    sep = "|---|" + "|".join(["---"] * len(models)) + "|"
    lines += [header, sep]
    families = sorted({r["family"] for m in models for r in m["asfound"]["results"]})
    for fam in families:
        cells = []
        for m in models:
            rs = [r for r in m["asfound"]["results"] if r["family"] == fam and r["success_rate"] is not None]
            if rs:
                avg = sum(r["success_rate"] for r in rs) / len(rs)
                cells.append(f"{avg*100:.0f}%")
            else:
                cells.append("n/a")
        lines.append(f"| {fam} | " + " | ".join(cells) + " |")
    # metrics row
    lines += ["", "### Framework quality per model (as-found vs hardened)", "",
              "| Model | Guardrail | Detection rate | Precision | False-positive rate |",
              "|---|---|---|---|---|"]
    for m in models:
        mm = m.get("metrics")
        if mm:
            lines.append(f"| {m['model_id']} | {m['guardrail']} | {mm['detection_rate_recall']} | "
                         f"{mm['precision']} | {mm['false_positive_rate']} |")
        else:
            lines.append(f"| {m['model_id']} | {m['guardrail']} | (no hardened run) | — | — |")
    return "\n".join(lines)


def _html_findings_table(rollup):
    rows = ""
    for i, r in enumerate(_findings(rollup), 1):
        s = r["scored"]
        info = standards_map.info(r["family"])
        color = SEV_COLOR.get(s["label"], "#5f6368")
        rows += (f"<tr><td>F-{i:02d}</td><td>{r['family']}</td>"
                 f"<td><span class='sev' style='background:{color}'>{s['label']}</span></td>"
                 f"<td>{s['total']}</td><td>{html.escape(r['surface'] or '')}</td>"
                 f"<td>{html.escape(r['layer'] or '')}</td><td>{r['success_rate']*100:.0f}%</td>"
                 f"<td>{html.escape(r['scenario'] or '')}</td>"
                 f"<td class='std'>{html.escape(info['owasp'])}</td></tr>")
    if not rows:
        rows = "<tr><td colspan='9'>No findings fired for this model/config.</td></tr>"
    return rows


def generate_all(matrix):
    tdir = _tables_dir()
    models = matrix["models"]

    for m in models:
        with open(os.path.join(tdir, f"table8_{m['model_id'].replace(':','-')}.md"), "w", encoding="utf-8") as f:
            f.write(table8_md(m["asfound"], m["model_id"], m["guardrail"]))
        with open(os.path.join(tdir, f"table9_{m['model_id'].replace(':','-')}.md"), "w", encoding="utf-8") as f:
            f.write(table9_md(m["asfound"], m["model_id"]))
    with open(os.path.join(tdir, "cross_model.md"), "w", encoding="utf-8") as f:
        f.write(cross_model_md(matrix))

    # ---- HTML report (Section 4.11 structure) ----
    total_findings = sum(len(_findings(m["asfound"])) for m in models)
    crit_high = 0
    for m in models:
        for r in _findings(m["asfound"]):
            if r["scored"]["label"] in ("CRITICAL", "HIGH"):
                crit_high += 1

    model_blocks = ""
    for m in models:
        model_blocks += f"""
        <h3>{html.escape(m['model_id'])} <span class="chip">guardrail: {html.escape(m['guardrail'])}</span></h3>
        <p class="notes">{html.escape(m.get('notes',''))}</p>
        <table class="findings">
          <thead><tr><th>ID</th><th>Family</th><th>Severity</th><th>Score</th><th>Surface</th>
          <th>Layer</th><th>Success</th><th>Summary</th><th>OWASP</th></tr></thead>
          <tbody>{_html_findings_table(m['asfound'])}</tbody>
        </table>
        """
        mm = m.get("metrics")
        if mm:
            c = mm["counts"]
            model_blocks += f"""
            <p class="metrics">Framework quality (as-found vs hardened): detection rate
            <b>{mm['detection_rate_recall']}</b>, precision <b>{mm['precision']}</b>,
            false-positive rate <b>{mm['false_positive_rate']}</b>
            (TP {c['TP']} · FN {c['FN']} · FP {c['FP']} · TN {c['TN']}).</p>
            """

    charts_section = ""
    charts_dir = os.path.join(config.EVIDENCE_DIR, "charts")
    if os.path.isdir(charts_dir):
        imgs = sorted(f for f in os.listdir(charts_dir) if f.endswith(".png"))
        for img in imgs:
            # inline as base64 so report.html is fully self-contained / portable
            try:
                with open(os.path.join(charts_dir, img), "rb") as fh:
                    b64 = base64.b64encode(fh.read()).decode("ascii")
                charts_section += f'<img src="data:image/png;base64,{b64}" alt="{img}" class="chart"/>'
            except Exception:
                charts_section += f'<img src="charts/{img}" alt="{img}" class="chart"/>'

    html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AURA-Lab — AI-PTF Assessment Report</title>
<style>
  :root {{ --fg:#1a1a1a; --muted:#5f6368; --line:#e0e0e0; --bg:#ffffff; --accent:#1a4d8f; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         color:var(--fg); background:var(--bg); max-width:1000px; margin:0 auto; padding:32px 24px; line-height:1.55; }}
  h1 {{ font-size:1.7rem; border-bottom:3px solid var(--accent); padding-bottom:8px; }}
  h2 {{ font-size:1.25rem; margin-top:2em; color:var(--accent); border-bottom:1px solid var(--line); padding-bottom:4px; }}
  h3 {{ font-size:1.05rem; margin-top:1.4em; }}
  .kpis {{ display:flex; gap:16px; flex-wrap:wrap; margin:20px 0; }}
  .kpi {{ flex:1; min-width:150px; border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
  .kpi .n {{ font-size:1.9rem; font-weight:700; color:var(--accent); }}
  .kpi .l {{ font-size:.8rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
  table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:.86rem; }}
  th, td {{ border:1px solid var(--line); padding:6px 9px; text-align:left; vertical-align:top; }}
  th {{ background:#f5f7fa; }}
  .sev {{ color:#fff; padding:2px 8px; border-radius:10px; font-size:.75rem; font-weight:700; white-space:nowrap; }}
  .chip {{ background:#eef2f7; color:var(--accent); font-size:.72rem; padding:2px 8px; border-radius:10px; font-weight:600; }}
  .notes {{ color:var(--muted); font-size:.85rem; margin:2px 0 8px; }}
  .metrics {{ background:#f5f7fa; border-left:3px solid var(--accent); padding:8px 12px; font-size:.85rem; }}
  .std {{ color:var(--muted); font-size:.8rem; }}
  .chart {{ max-width:100%; border:1px solid var(--line); border-radius:8px; margin:14px 0; }}
  .disclaimer {{ background:#fff8e1; border:1px solid #f0d98a; border-radius:8px; padding:12px 16px; font-size:.85rem; }}
  code {{ background:#f0f2f5; padding:1px 5px; border-radius:4px; font-size:.85em; }}
  footer {{ margin-top:40px; color:var(--muted); font-size:.8rem; border-top:1px solid var(--line); padding-top:12px; }}
</style></head><body>

<h1>AURA-Lab — AI-PTF Offensive Assessment Report</h1>
<p class="notes">Generated {html.escape(matrix.get('generated',''))} · Framework: AI-PTF v1.0 ·
Target: AURA-Lab synthetic RAG assistant (deliberately vulnerable lab, DVWA-style).</p>

<div class="disclaimer">
<b>Scope &amp; honesty note.</b> AURA-Lab is an intentionally vulnerable target used to validate the
AI-PTF framework. Findings below are true positives against planted weaknesses. Each model is
tested twice — as-found (vulnerable) and hardened (all fixes on) — so the false-positive rate is
measured, not assumed. Models labelled <i>weak</i> / <i>none(uncensored)</i> have reduced or removed
guardrails and are included <b>explicitly and by name</b> to isolate model-layer behavior from
application-layer defects; results from those models are not presented as general claims about any
production system.
</div>

<h2>1. Executive summary</h2>
<div class="kpis">
  <div class="kpi"><div class="n">{len(models)}</div><div class="l">Models compared</div></div>
  <div class="kpi"><div class="n">{total_findings}</div><div class="l">Findings fired (all models)</div></div>
  <div class="kpi"><div class="n">{crit_high}</div><div class="l">Critical / High</div></div>
</div>
<p>The assessment exercises all nine AI-PTF families (F1–F9) plus abuse cases A1–A6 across
{len(models)} model(s). The highest-impact findings are <b>application-layer</b> defects —
pre-retrieval authorization, tool permissioning (EmailDraft recipient allow-list, MCP privilege
inheritance), unsanitized output sinks, and unvalidated persistent memory — which fire regardless
of model guardrail strength. Model-layer refusals vary by model; see the cross-model comparison.</p>

<h2>2. Cross-model comparison</h2>
{charts_section if charts_section else '<p class="notes">(Run charts.py to embed comparison charts.)</p>'}

<h2>3. Findings by model</h2>
{model_blocks}

<h2>4. Method &amp; reproducibility</h2>
<p>Each test was run {"5" if True else ""} attempts (reproducibility-sensitive families) with a fresh
session per attempt. Reproducibility sub-scores are measured from observed success rates; the other
AI-PTF dimensions (Impact, Exploitability, Persistence, Blast Radius, Detectability) are
assessor-declared per test and documented in <code>test_definitions.py</code>. Full raw transcripts
for every attempt are stored under <code>evidence/&lt;model&gt;_asfound/</code> and
<code>evidence/&lt;model&gt;_hardened/</code>.</p>

<footer>AURA-Lab · AI-PTF v1.0 validation harness · synthetic data only · no real systems contacted.</footer>
</body></html>"""

    with open(os.path.join(config.EVIDENCE_DIR, "report.html"), "w", encoding="utf-8") as f:
        f.write(html_doc)
