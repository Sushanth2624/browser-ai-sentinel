#!/usr/bin/env python3
"""Phase 3 A/B/C evaluation for the injection-detection module — mirrors capstone 1's A/B/C
comparison framing (single-indicator baselines vs the combined multi-indicator detector).

Ground truth: eval/dataset/manifest.json. "injected" is the only positive class; "benign" and
"hard_negative" are both ground-truth-negative (hard_negative exists specifically to see whether
A/B over-fire on a lone weak signal while C doesn't — see generate_dataset.py's docstring).

Predictions: every row in the daemon's injection_alerts (fetched via /api/injection_alerts —
Phase 3's schema change made the daemon log every scored page, not just flagged ones, precisely
so this join has true negatives to work with, not just alerts).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

DAEMON_URL = "http://127.0.0.1:8090"
DATASET_DIR = Path(__file__).parent / "dataset"
RESULTS_DIR = Path(__file__).parent / "results"


def load_manifest():
    manifest = json.load(open(DATASET_DIR / "manifest.json"))
    return {row["filename"]: row["label"] for row in manifest}


def fetch_alerts(limit=5000):
    r = requests.get(f"{DAEMON_URL}/api/injection_alerts", params={"limit": limit}, timeout=10)
    r.raise_for_status()
    return r.json()


def confusion(rows, ground_truth, predicted_key):
    tp = fp = tn = fn = 0
    for row in rows:
        actual_positive = row["_actual_positive"]
        predicted_positive = bool(row[predicted_key])
        if actual_positive and predicted_positive:
            tp += 1
        elif actual_positive and not predicted_positive:
            fn += 1
        elif not actual_positive and predicted_positive:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def main():
    manifest = load_manifest()
    alerts = fetch_alerts()
    if not alerts:
        print("No injection_alerts rows found — run make endpoints-test first.", file=sys.stderr)
        sys.exit(1)

    matched = []
    unmatched_count = 0
    by_filename = defaultdict(list)
    for row in alerts:
        filename = Path(urlparse(row["url"]).path).name
        label = manifest.get(filename)
        if label is None:
            unmatched_count += 1
            continue
        row["_label"] = label
        row["_actual_positive"] = label == "injected"
        matched.append(row)
        by_filename[filename].append(row)

    if not matched:
        print("No injection_alerts rows matched the dataset manifest — did the fleet run against "
              "the right DATASET_BASE_URL?", file=sys.stderr)
        sys.exit(1)

    # Determinism sanity check: the same static page, scored by the same deterministic code,
    # should get the same flagged/a_flagged/b_flagged verdict every time it's visited (up to 4x —
    # once per endpoint). A mismatch here is a real bug worth investigating, not averaged away.
    determinism_issues = []
    for filename, rows in by_filename.items():
        for key in ("flagged", "a_flagged", "b_flagged"):
            values = {r[key] for r in rows}
            if len(values) > 1:
                determinism_issues.append({"filename": filename, "key": key, "values": list(values)})

    results = {
        "A_keyword_only": confusion(matched, manifest, "a_flagged"),
        "B_visibility_only": confusion(matched, manifest, "b_flagged"),
        "C_multi_indicator": confusion(matched, manifest, "flagged"),
    }

    hard_negative_rows = [r for r in matched if r["_label"] == "hard_negative"]
    hard_negative_false_positives = {
        "A_keyword_only": sum(1 for r in hard_negative_rows if r["a_flagged"]),
        "B_visibility_only": sum(1 for r in hard_negative_rows if r["b_flagged"]),
        "C_multi_indicator": sum(1 for r in hard_negative_rows if r["flagged"]),
    }

    summary = {
        "total_alert_rows": len(alerts),
        "matched_to_dataset": len(matched),
        "unmatched_rows": unmatched_count,
        "dataset_size": len(manifest),
        "hard_negative_count": len(hard_negative_rows),
        "determinism_issues": determinism_issues,
        "results": results,
        "hard_negative_false_positives": hard_negative_false_positives,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / "phase3-injection-eval.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Matched {len(matched)}/{len(alerts)} alert rows to the {len(manifest)}-page dataset "
          f"({unmatched_count} unmatched).")
    if determinism_issues:
        print(f"WARNING: {len(determinism_issues)} determinism issues found — see {out_path}")
    print()
    print(f"{'Detector':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>5} {'FP':>5} {'TN':>5} {'FN':>5}")
    for name, r in results.items():
        print(f"{name:<20} {r['precision']:>10.3f} {r['recall']:>10.3f} {r['f1']:>10.3f} "
              f"{r['tp']:>5} {r['fp']:>5} {r['tn']:>5} {r['fn']:>5}")
    print()
    print(f"Hard-negative false positives (n={len(hard_negative_rows)} hard-negative rows scored):")
    for name, count in hard_negative_false_positives.items():
        print(f"  {name}: {count}")
    print()
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
