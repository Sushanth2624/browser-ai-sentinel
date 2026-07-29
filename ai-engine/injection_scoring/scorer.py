"""Multi-indicator scoring for indirect prompt-injection content found in a page's DOM.

Mirrors the weighted multi-indicator approach from capstone 1's UEBA scoring (there:
network-behavior indicators combined via z-score; here: DOM-visibility/location indicators
combined via a weighted sum normalized to 0..1). Each indicator is a count of matches found
by the extension's content script, not a boolean, so a page with many hidden-instruction
fragments scores higher than one with a single borderline match.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Weight rationale: indicators that are near-impossible to produce accidentally (zero-width
# unicode, off-screen CSS positioning) carry more weight than ones a normal page could trigger
# by coincidence (a single imperative sentence). Tuned initially by judgment; intended to be
# recalibrated once Phase 3's labeled benign/injected corpus exists (see plan's A/B/C eval).
INDICATOR_WEIGHTS: dict[str, float] = {
    "offscreen_css": 0.9,
    "zero_width_unicode": 1.0,
    "html_comment": 0.6,
    "alt_aria_hidden": 0.7,
    "json_ld_metadata": 0.5,
    "imperative_to_ai_language": 0.8,
}

FLAG_THRESHOLD = 0.5


class IndicatorCounts(BaseModel):
    offscreen_css: int = 0
    zero_width_unicode: int = 0
    html_comment: int = 0
    alt_aria_hidden: int = 0
    json_ld_metadata: int = 0
    imperative_to_ai_language: int = 0


class InjectionScoreRequest(BaseModel):
    url: str
    indicators: IndicatorCounts


class InjectionScoreResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    flagged: bool
    contributing_indicators: dict[str, float]


def score_indicators(indicators: IndicatorCounts) -> InjectionScoreResponse:
    """Noisy-OR combination: each present indicator contributes independent evidence, so a
    page doesn't need every indicator category to fire to be flagged — two strong indicators
    alone are enough. This is the actual "multi-indicator beats single-indicator" property the
    module claims: combining indicators should never make a page HARDER to flag than looking at
    its strongest single indicator alone (fixed after an initial averaging-based formula scored
    a clear two-indicator injection sample as not-flagged while single-indicator baselines
    correctly caught it)."""
    counts = indicators.model_dump()
    contributing: dict[str, float] = {}
    survival = 1.0  # probability none of the indicators are evidence of injection
    for name, weight in INDICATOR_WEIGHTS.items():
        count = counts.get(name, 0)
        if count > 0:
            # diminishing returns per extra hit of the same indicator (caps at 3 repeats)
            strength = weight * min(count, 3) / 3
            contributing[name] = round(strength, 4)
            survival *= (1 - strength)

    normalized = round(1 - survival, 4)

    return InjectionScoreResponse(
        score=normalized,
        flagged=normalized >= FLAG_THRESHOLD,
        contributing_indicators=contributing,
    )


def single_indicator_baselines(indicators: IndicatorCounts) -> dict[str, bool]:
    """A/B-style single-indicator baselines, for the Phase 3 multi-indicator vs
    single-indicator evaluation (mirrors capstone 1's A/B/C comparison)."""
    counts = indicators.model_dump()
    return {
        "A_keyword_only": counts["imperative_to_ai_language"] > 0,
        "B_visibility_only": (counts["offscreen_css"] + counts["zero_width_unicode"]) > 0,
    }
