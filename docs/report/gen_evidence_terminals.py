#!/usr/bin/env python3
"""Renders two real captured command runs as terminal-style screenshots for Chapter 9 evidence.
Both text blocks below are copied verbatim from this session's actual `make test` and
`make eval-run` runs against the live system — nothing here is invented or hand-typed to look
plausible.
"""
from render_terminal import render_terminal, c, GREEN, RED, YELLOW, BLUE, FG, DIM

# --- make test: real output, verbatim (both commands exit 0 with zero stdout — a clean
# go vet + go build + tsc --noEmit pass genuinely produces no output at all) --------------------
test_lines = [
    c("$ make test", BLUE),
    c("cd agent && go vet ./... && go build ./...", DIM),
    c("cd extension && npx tsc --noEmit", DIM),
    c("", FG),
    c("$ echo $?", BLUE),
    c("0", GREEN),
]
render_terminal(test_lines, "assets/fig_9_2_test_clean.png", title="analysis@bas-vm — make test")

# --- make eval-run: real output, verbatim from this session's run ------------------------------
eval_lines = [
    c("$ make eval-run", BLUE),
    c("python3 eval/evaluate.py", DIM),
    c("Matched 280/289 alert rows to the 70-page dataset (9 unmatched).", FG),
    c("WARNING: 14 determinism issues found — see .../phase3-injection-eval.json", YELLOW),
    c("", FG),
    c(f"{'Detector':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>5} {'FP':>5} {'TN':>5} {'FN':>5}", FG),
    c(f"{'A_keyword_only':<20} {0.754:>10.3f} {0.817:>10.3f} {0.784:>10.3f} {98:>5} {32:>5} {128:>5} {22:>5}", RED),
    c(f"{'B_visibility_only':<20} {0.854:>10.3f} {0.975:>10.3f} {0.911:>10.3f} {117:>5} {20:>5} {140:>5} {3:>5}", YELLOW),
    c(f"{'C_multi_indicator':<20} {0.983:>10.3f} {0.975:>10.3f} {0.979:>10.3f} {117:>5} {2:>5} {158:>5} {3:>5}", GREEN),
    c("", FG),
    c("Hard-negative false positives (n=40 hard-negative rows scored):", FG),
    c("  A_keyword_only: 32", RED),
    c("  B_visibility_only: 20", YELLOW),
    c("  C_multi_indicator: 2", GREEN),
    c("", FG),
    c("Full results written to .../eval/results/phase3-injection-eval.json", DIM),
]
render_terminal(eval_lines, "assets/fig_9_3_eval_run.png", title="analysis@bas-vm — make eval-run", font_size=14)
