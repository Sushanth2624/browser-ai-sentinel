"""Regex/entity-rule PII and secret detection for outbound content headed to an AI service.

Deliberately simple for Phase 1 (regex + a Luhn check for card numbers to cut false positives).
Upgrade path to NER (e.g. Presidio) is noted in the plan but not built yet — flagged here so the
report doesn't overclaim recall on entities regex can't reliably catch (names, addresses).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_API_KEY_RE = re.compile(
    r"\b(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|AIza[0-9A-Za-z\-_]{35})\b"
)

ENTITY_PATTERNS: dict[str, re.Pattern] = {
    "email": _EMAIL_RE,
    "phone": _PHONE_RE,
    "credit_card": _CARD_RE,
    "ssn": _SSN_RE,
    "api_key_or_secret": _API_KEY_RE,
}


def _luhn_valid(digits: str) -> bool:
    digits = [int(d) for d in digits if d.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


class PIIMatch(BaseModel):
    type: str
    count: int


class PIIClassifyRequest(BaseModel):
    text: str


class PIIClassifyResponse(BaseModel):
    verdict: str  # "clean" | "flagged"
    matched_entities: list[PIIMatch]


def classify_text(text: str) -> PIIClassifyResponse:
    matches: list[PIIMatch] = []
    for entity_type, pattern in ENTITY_PATTERNS.items():
        found = pattern.findall(text)
        if entity_type == "credit_card":
            found = [f for f in found if _luhn_valid(f)]
        if found:
            matches.append(PIIMatch(type=entity_type, count=len(found)))

    verdict = "flagged" if matches else "clean"
    return PIIClassifyResponse(verdict=verdict, matched_entities=matches)
