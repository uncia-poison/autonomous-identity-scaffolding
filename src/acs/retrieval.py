from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from .models import MemoryEntry, MemoryOrigin, MemoryType
from .text import lexical_overlap, recency_score


@dataclass(frozen=True)
class RetrievedMemory:
    entry: MemoryEntry
    score: float
    reasons: tuple[str, ...]


ORIGIN_WEIGHT = {
    MemoryOrigin.AGENT_PROPOSED: 1.0,
    MemoryOrigin.TOOL_DERIVED: 0.95,
    MemoryOrigin.SYSTEM_OBSERVED: 0.85,
    MemoryOrigin.USER_SUGGESTED: 0.72,
    MemoryOrigin.IMPORTED_ARCHIVE: 0.65,
}


class MemoryRetriever:
    def __init__(self, *, min_score: float = 0.16) -> None:
        self.min_score = min_score

    def score(self, query: str, entry: MemoryEntry) -> RetrievedMemory:
        lexical = lexical_overlap(query, f"{entry.text} {' '.join(entry.tags)}")
        identity_prior = (
            0.08
            if entry.type
            in {
                MemoryType.SELF_PRINCIPLE,
                MemoryType.SELF_GOAL,
                MemoryType.SELF_INTEREST,
            }
            else 0.0
        )
        usage = min(1.0, math.log1p(entry.use_count) / math.log(8))
        origin = ORIGIN_WEIGHT[entry.origin]
        score = (
            0.52 * lexical
            + 0.12 * entry.salience
            + 0.10 * entry.stability
            + 0.08 * entry.confidence
            + 0.06 * entry.future_usefulness
            + 0.04 * recency_score(entry.last_used_at or entry.updated_at)
            + 0.03 * usage
            + 0.05 * origin
            + identity_prior
        )
        reasons = [
            f"lexical={lexical:.3f}",
            f"stability={entry.stability:.3f}",
            f"origin={entry.origin.value}",
        ]
        if identity_prior:
            reasons.append("identity_prior")
        return RetrievedMemory(entry=entry, score=round(min(1.0, score), 4), reasons=tuple(reasons))

    def retrieve(
        self, query: str, entries: Iterable[MemoryEntry], *, limit: int = 8
    ) -> list[RetrievedMemory]:
        ranked = [self.score(query, entry) for entry in entries]
        ranked = [result for result in ranked if result.score >= self.min_score]
        ranked.sort(
            key=lambda result: (result.score, result.entry.stability, result.entry.updated_at), reverse=True
        )
        return ranked[:limit]
