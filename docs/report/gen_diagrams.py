#!/usr/bin/env python3
"""Generates the architecture/data-flow/module diagrams for Chapter 7. Fresh script, matplotlib,
unified light-blue fill for all architecture-style boxes — applying, proactively this time, the
same lesson from capstone 1's mentor review (unify flowchart colors, don't use a rainbow
categorical palette for a structural diagram) rather than waiting for the same correction twice.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.path import Path

FILL = "#dbe8f7"
BORDER = "#6f9bc7"
TEXT = "#14181c"
ACCENT_FILL = "#fde8c8"
ACCENT_BORDER = "#d9a441"
ASSETS = "assets"

import os
os.makedirs(ASSETS, exist_ok=True)


def box(ax, x, y, w, h, text, fill=FILL, border=BORDER, fontsize=9.5, bold=False):
    b = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=1.4, edgecolor=border, facecolor=fill, zorder=2,
    )
    ax.add_patch(b)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, color=TEXT, weight="bold" if bold else "normal",
             wrap=True, zorder=3)
    return (x, y, w, h)


def arrow(ax, start, end, label="", curve=0.0, fontsize=8.5):
    a = FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=14,
        linewidth=1.3, color="#4a5057",
        connectionstyle=f"arc3,rad={curve}", zorder=1,
    )
    ax.add_patch(a)
    if label:
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        ax.text(mx, my + 0.08, label, ha="center", va="bottom", fontsize=fontsize, color="#4a5057")


def new_ax(w=10, h=6.2):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


# ---------------------------------------------------------------------------
# Fig 7.1 — System architecture
# ---------------------------------------------------------------------------
fig, ax = new_ax(11, 6.0)

box(ax, 0.4, 4.4, 3.0, 1.2, "Chrome Extension\n(TypeScript, MV3)\ncontent scripts + background", bold=True)
box(ax, 4.0, 4.4, 2.6, 1.2, "nmhost\n(ephemeral, native\nmessaging shim)")
box(ax, 7.1, 4.4, 3.2, 1.2, "Go daemon\n(persistent, :8090)", bold=True)

box(ax, 7.1, 2.5, 3.2, 1.1, "Python ai-engine\n(FastAPI, :8100)\nscoring + PII + ATLAS")
box(ax, 4.0, 2.5, 2.6, 1.1, "Postgres\n(:5433)", bold=True)
box(ax, 0.4, 2.5, 3.0, 1.1, "React dashboard\n(:3000)")

box(ax, 4.0, 0.3, 2.6, 1.2, "Zeek + Suricata\n(bas-zeek, bas-zeek-lo,\nbas-suricata)", bold=True)
box(ax, 7.1, 0.3, 3.2, 1.2, "Mock AI endpoints\n(sensor/mock-ai)\nshadow-AI test targets")
box(ax, 0.4, 0.3, 3.0, 1.2, "Real AI platforms\n(claude.ai, chatgpt.com, ...)")

arrow(ax, (3.4, 5.0), (4.0, 5.0), "chrome.runtime\n.connectNative")
arrow(ax, (6.6, 5.0), (7.1, 5.0), "stdio <-> HTTP")
arrow(ax, (8.7, 4.4), (8.7, 3.6), "HTTP")
arrow(ax, (7.1, 3.0), (6.6, 3.0), "writes")
arrow(ax, (4.0, 3.0), (3.4, 3.0), "reads")
arrow(ax, (5.3, 2.5), (5.3, 1.5), "tails ssl.log / eve.json")
# Both AI-traffic sources are only ever passively OBSERVED by the sensor watching the NIC —
# neither one has an active connection to Zeek/Suricata, so both arrows point the same way with
# the same "passive capture" label, avoiding the earlier version's implication that the mock
# endpoints send data TO the sensor (they don't; the sensor watches the wire).
arrow(ax, (1.9, 1.5), (4.6, 0.9), "passive capture\n(SNI/JA3/JA4)", curve=-0.15)
arrow(ax, (7.1, 0.9), (6.6, 0.9), "passive capture\n(SNI/JA3/JA4)")

ax.text(5.5, 5.75, "Browser AI Sentinel — System Architecture", ha="center", fontsize=13, weight="bold")
fig.tight_layout()
fig.savefig(f"{ASSETS}/fig_7_1_architecture.png", dpi=200)
plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 7.2 — Data flow: browser event to stored verdict
# ---------------------------------------------------------------------------
fig, ax = new_ax(11, 4.4)

steps = [
    ("Page loads /\nfetch() called", 0.3),
    ("Content script\nscans DOM /\ncaptures body", 2.3),
    ("Background\nservice worker", 4.3),
    ("nmhost", 6.3),
    ("Go daemon", 8.1),
]
for text, x in steps:
    box(ax, x, 2.6, 1.7, 1.1, text, fontsize=9)
for i in range(len(steps) - 1):
    x0 = steps[i][1] + 1.7
    x1 = steps[i + 1][1]
    arrow(ax, (x0, 3.15), (x1, 3.15))

box(ax, 5.0, 0.4, 2.0, 1.1, "ai-engine\nscore / classify", fontsize=9)
box(ax, 7.8, 0.4, 2.0, 1.1, "Postgres\nrow written", fontsize=9)
arrow(ax, (8.9, 2.6), (6.0, 1.5), "", curve=0.15)
arrow(ax, (6.0, 0.95), (7.8, 0.95), "verdict")
arrow(ax, (9.6, 1.5), (9.6, 2.6), "ack / banner\nor approval gate", curve=0.3)

ax.text(5.5, 4.15, "Data Flow: Browser Event to Stored Verdict", ha="center", fontsize=13, weight="bold")
fig.tight_layout()
fig.savefig(f"{ASSETS}/fig_7_2_dataflow.png", dpi=200)
plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 7.3 — Module / repository dependency diagram
# ---------------------------------------------------------------------------
fig, ax = new_ax(10.5, 5.3)

box(ax, 0.4, 3.7, 2.6, 1.0, "extension/\n(TypeScript)", bold=True)
box(ax, 3.4, 3.7, 2.6, 1.0, "agent/\n(Go)", bold=True)
box(ax, 6.4, 3.7, 2.6, 1.0, "ai-engine/\n(Python)", bold=True)

box(ax, 0.4, 2.0, 2.6, 1.0, "sensor/\n(Zeek/Suricata configs)")
box(ax, 3.4, 2.0, 2.6, 1.0, "db/\n(schema.sql)")
box(ax, 6.4, 2.0, 2.6, 1.0, "dashboard/\n(React/TS)")

box(ax, 0.4, 0.3, 2.6, 1.0, "endpoints/\n(test fleet)")
box(ax, 3.4, 0.3, 2.6, 1.0, "eval/\n(dataset + evaluator)")
box(ax, 6.4, 0.3, 2.6, 1.0, "docs/report/\n(this document)", fill=ACCENT_FILL, border=ACCENT_BORDER)

arrow(ax, (1.7, 3.7), (2.6, 3.0), "", curve=0.1)
arrow(ax, (4.7, 3.7), (4.7, 3.0))
arrow(ax, (7.7, 3.7), (7.7, 3.0))
arrow(ax, (2.6, 2.5), (1.7, 2.0), "", curve=-0.1)
arrow(ax, (1.7, 1.3), (1.7, 2.0), "drives")
arrow(ax, (4.7, 1.3), (4.7, 2.0), "serves via http.server", fontsize=7.8)
arrow(ax, (4.7, 2.0), (7.7, 1.3), "", curve=-0.2)

ax.text(5.25, 5.05, "Module / Repository Dependency Diagram", ha="center", fontsize=13, weight="bold")
fig.tight_layout()
fig.savefig(f"{ASSETS}/fig_7_3_modules.png", dpi=200)
plt.close(fig)

print("Wrote fig_7_1_architecture.png, fig_7_2_dataflow.png, fig_7_3_modules.png to", ASSETS)
