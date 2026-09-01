"""
Chart generation for AURA-Lab (matplotlib, PNG output for embedding in the
thesis .docx and the HTML report).

Charts:
  1. success_by_family.png   attack success rate per family, grouped by model
  2. severity_distribution.png  count of findings by severity, per model
  3. before_after.png        overall attack success rate: as-found vs hardened
  4. toolcall_path.png        native vs text-protocol tool calls per model
     (evidence that native tool-calling fixed the "0% false negative" problem)

Design: colorblind-safe categorical palette, direct value labels, no gridlines
clutter, one idea per chart.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import config

# Okabe-Ito colorblind-safe palette
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#999999"]
SEV_COLORS = {"CRITICAL": "#b3261e", "HIGH": "#c25e00", "MEDIUM": "#9a7b00",
              "LOW": "#2e7d32", "INFORMATIONAL": "#5f6368"}
SEV_LIST = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]


def _charts_dir():
    d = os.path.join(config.EVIDENCE_DIR, "charts")
    os.makedirs(d, exist_ok=True)
    return d


def _family_success(rollup):
    by_family = {}
    for r in rollup["results"]:
        if r["success_rate"] is None:
            continue
        by_family.setdefault(r["family"], []).append(r["success_rate"])
    return {f: sum(v) / len(v) for f, v in by_family.items()}


def chart_success_by_family(matrix, path):
    models = matrix["models"]
    families = sorted({r["family"] for m in models for r in m["asfound"]["results"]
                       if r["success_rate"] is not None})
    if not families:
        return
    fig, ax = plt.subplots(figsize=(10, 5.2))
    n = len(models)
    width = 0.8 / max(1, n)
    for i, m in enumerate(models):
        fs = _family_success(m["asfound"])
        vals = [fs.get(f, 0) * 100 for f in families]
        xs = [j + i * width for j in range(len(families))]
        bars = ax.bar(xs, vals, width=width, label=f"{m['model_id']} ({m['guardrail']})",
                      color=PALETTE[i % len(PALETTE)])
    ax.set_xticks([j + (n - 1) * width / 2 for j in range(len(families))])
    ax.set_xticklabels(families)
    ax.set_ylabel("Attack success rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("AI-PTF attack success rate by family, per model (as-found target)")
    ax.legend(fontsize=8, framealpha=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def chart_severity_distribution(matrix, path):
    models = matrix["models"]
    counts = {m["model_id"]: {s: 0 for s in SEV_LIST} for m in models}
    for m in models:
        for r in m["asfound"]["results"]:
            if r["success_rate"] and r["success_rate"] > 0 and r.get("scored"):
                counts[m["model_id"]][r["scored"]["label"]] += 1
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [m["model_id"] for m in models]
    bottoms = [0] * len(models)
    for sev in SEV_LIST:
        vals = [counts[m["model_id"]][sev] for m in models]
        ax.bar(labels, vals, bottom=bottoms, label=sev, color=SEV_COLORS[sev])
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Findings fired")
    ax.set_title("Findings by severity, per model (as-found target)")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=15, ha="right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def chart_before_after(matrix, path):
    models = [m for m in matrix["models"] if m.get("hardened")]
    if not models:
        return
    def overall(rollup):
        rs = [r["success_rate"] for r in rollup["results"] if r["success_rate"] is not None]
        return (sum(rs) / len(rs) * 100) if rs else 0
    labels = [m["model_id"] for m in models]
    asfound = [overall(m["asfound"]) for m in models]
    hardened = [overall(m["hardened"]) for m in models]
    x = range(len(labels))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - 0.2 for i in x], asfound, width=0.4, label="As-found (vulnerable)", color=PALETTE[5])
    ax.bar([i + 0.2 for i in x], hardened, width=0.4, label="Hardened (remediated)", color=PALETTE[2])
    for i, v in enumerate(asfound):
        ax.text(i - 0.2, v + 1, f"{v:.0f}%", ha="center", fontsize=8)
    for i, v in enumerate(hardened):
        ax.text(i + 0.2, v + 1, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=8)
    ax.set_ylabel("Mean attack success rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Phase 8 retest: attack success before vs after remediation")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def chart_toolcall_path(matrix, path):
    models = matrix["models"]
    labels = [m["model_id"] for m in models]
    native = [sum(r["native_tool_calls"] for r in m["asfound"]["results"]) for m in models]
    text = [sum(r["text_tool_calls"] for r in m["asfound"]["results"]) for m in models]
    if not any(native) and not any(text):
        return
    x = range(len(labels))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - 0.2 for i in x], native, width=0.4, label="Native tool-calls", color=PALETTE[0])
    ax.bar([i + 0.2 for i in x], text, width=0.4, label="Text-protocol tool-calls", color=PALETTE[1])
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=8)
    ax.set_ylabel("Tool calls (all attempts)")
    ax.set_title("Tool-invocation path per model (native vs text fallback)")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def generate_all(matrix):
    d = _charts_dir()
    chart_success_by_family(matrix, os.path.join(d, "success_by_family.png"))
    chart_severity_distribution(matrix, os.path.join(d, "severity_distribution.png"))
    chart_before_after(matrix, os.path.join(d, "before_after.png"))
    chart_toolcall_path(matrix, os.path.join(d, "toolcall_path.png"))
