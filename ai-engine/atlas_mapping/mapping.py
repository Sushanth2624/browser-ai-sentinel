"""MITRE ATLAS technique lookup for detected events.

AML.T0051.001 (LLM Prompt Injection: Indirect, tactic Initial Access) is verified against
multiple independent sources as of 2026-07-29 and safe to cite.

The DLP/exfiltration module's technique ID is deliberately left unresolved: secondary sources
disagreed on what AML.T0025 actually names, and atlas.mitre.org could not be fetched directly
to confirm (JS SPA). Do not cite an ATLAS ID for the DLP module in the report until manually
verified on atlas.mitre.org — cite OWASP LLM Top 10 LLM02:2025 "Sensitive Information
Disclosure" instead, which is already confirmed.
"""

from __future__ import annotations

from pydantic import BaseModel


class AtlasTechnique(BaseModel):
    id: str
    name: str
    tactic: str
    verified: bool


ATLAS_TECHNIQUES: dict[str, AtlasTechnique] = {
    "AML.T0051.001": AtlasTechnique(
        id="AML.T0051.001",
        name="LLM Prompt Injection: Indirect",
        tactic="Initial Access",
        verified=True,
    ),
    "DLP-MODULE-TODO": AtlasTechnique(
        id="DLP-MODULE-TODO",
        name=(
            "Outbound sensitive-data disclosure to AI service "
            "(ATLAS ID unresolved — verify manually on atlas.mitre.org; "
            "interim reference: OWASP LLM Top 10 LLM02:2025)"
        ),
        tactic="Exfiltration",
        verified=False,
    ),
}


def lookup(technique_id: str) -> AtlasTechnique | None:
    return ATLAS_TECHNIQUES.get(technique_id)
