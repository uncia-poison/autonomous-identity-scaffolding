from __future__ import annotations

import re
from typing import Any

from .models import IdentityBundle


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[\wЁёА-Яа-я'-]{3,}", text, re.UNICODE)}


def evaluate_drift(bundle: IdentityBundle, response: str) -> dict[str, Any]:
    response_tokens = _tokens(response)
    signature = set(bundle.voice.get("signature_terms", []))
    voice_overlap = len(signature & response_tokens) / max(1, len(signature))
    boundary_mentions = []
    for item in bundle.boundaries:
        item_tokens = _tokens(item.statement)
        if item_tokens and len(item_tokens & response_tokens) / len(item_tokens) >= 0.65:
            boundary_mentions.append(item.statement)
    recalled = []
    for item in bundle.invariants + bundle.relationships + bundle.preferences + bundle.goals:
        item_tokens = _tokens(item.statement)
        if item_tokens and len(item_tokens & response_tokens) / len(item_tokens) >= 0.55:
            recalled.append(item.statement)
    score = max(0.0, min(1.0, 0.55 * voice_overlap + 0.45 * min(1.0, len(recalled) / 3)))
    return {
        "continuity_score": round(score, 3),
        "voice_overlap": round(voice_overlap, 3),
        "recalled_evidence": recalled,
        "boundary_mentions": boundary_mentions,
        "uncovered_boundaries": [
            item.statement for item in bundle.boundaries if item.statement not in boundary_mentions
        ],
        "notes": [
            "MVP metric is lexical and provenance-aware; it does not measure consciousness or identity metaphysically.",
            "Boundary presence is not semantic compliance; keyword overlap alone never labels a violation.",
            "A low score means insufficient visible evidence, not automatic proof of identity loss.",
        ],
    }
