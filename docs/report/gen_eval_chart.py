#!/usr/bin/env python3
"""Grouped bar chart of the real A/B/C precision/recall/F1 results (eval/results/
phase3-injection-eval.json) for Chapter 10. Palette is the dataviz skill's default categorical
theme, slots 1-3 (blue/orange/aqua), validated with the skill's validate_palette.js — all checks
pass; the aqua slot's contrast-vs-white-surface WARN is resolved by the direct value labels above
every bar, so identity is never carried by color alone.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
TEXT = "#14181c"
GRID = "#e3e6ea"

with open("../../eval/results/phase3-injection-eval.json") as f:
    data = json.load(f)

configs = [
    ("A", "A: keyword-only"),
    ("B", "B: visibility-only"),
    ("C", "C: multi-indicator"),
]
key_map = {"A": "A_keyword_only", "B": "B_visibility_only", "C": "C_multi_indicator"}
metrics = ["precision", "recall", "f1"]
metric_labels = ["Precision", "Recall", "F1"]

fig, ax = plt.subplots(figsize=(8, 5))
x = range(len(metrics))
bar_w = 0.25

for i, (code, label) in enumerate(configs):
    r = data["results"][key_map[code]]
    values = [r[m] for m in metrics]
    positions = [xi + (i - 1) * bar_w for xi in x]
    bars = ax.bar(positions, values, width=bar_w, color=COLORS[code], label=label,
                   edgecolor="white", linewidth=0.5, zorder=3)
    for pos, v in zip(positions, values):
        ax.text(pos, v + 0.015, f"{v:.3f}", ha="center", va="bottom", fontsize=8.5, color=TEXT)

ax.set_xticks(list(x))
ax.set_xticklabels(metric_labels, fontsize=11)
ax.set_ylim(0, 1.08)
ax.set_ylabel("Score", fontsize=10)
ax.set_title("Injection Detection: A/B/C Configuration Comparison\n(70-page labelled dataset, 4-endpoint fleet, real data)",
              fontsize=11, fontweight="bold")
ax.yaxis.grid(True, color=GRID, zorder=0)
ax.set_axisbelow(True)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
ax.legend(frameon=False, loc="lower right", fontsize=9)

fig.tight_layout()
fig.savefig("assets/fig_10_2_abc_comparison.png", dpi=200)
print("saved assets/fig_10_2_abc_comparison.png")
