"""AI engine — the classification/mapping brain of Browser AI Sentinel.

Called only by the Go daemon (agent/cmd/daemon), never directly by the extension.
Run: uvicorn api:app --host 127.0.0.1 --port 8100
"""

from __future__ import annotations

from fastapi import FastAPI

from atlas_mapping.mapping import ATLAS_TECHNIQUES, lookup as atlas_lookup
from injection_scoring.scorer import (
    InjectionScoreRequest,
    InjectionScoreResponse,
    score_indicators,
    single_indicator_baselines,
)
from pii_detection.detector import PIIClassifyRequest, PIIClassifyResponse, classify_text

app = FastAPI(title="Browser AI Sentinel — AI Engine")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score/injection", response_model=InjectionScoreResponse)
def score_injection(req: InjectionScoreRequest):
    return score_indicators(req.indicators)


@app.post("/score/injection/baselines")
def score_injection_baselines(req: InjectionScoreRequest):
    """Single-indicator A/B baselines alongside the C (multi-indicator) score, for eval."""
    combined = score_indicators(req.indicators)
    baselines = single_indicator_baselines(req.indicators)
    return {"C_multi_indicator": combined.model_dump(), **baselines}


@app.post("/classify/pii", response_model=PIIClassifyResponse)
def classify_pii(req: PIIClassifyRequest):
    return classify_text(req.text)


@app.get("/atlas/techniques")
def list_atlas_techniques():
    return {tid: t.model_dump() for tid, t in ATLAS_TECHNIQUES.items()}


@app.get("/atlas/techniques/{technique_id}")
def get_atlas_technique(technique_id: str):
    technique = atlas_lookup(technique_id)
    if technique is None:
        return {"error": "not found"}
    return technique.model_dump()
