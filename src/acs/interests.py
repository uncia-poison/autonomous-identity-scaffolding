from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import InterestUpdate
from .text import lexical_overlap


@dataclass(frozen=True)
class InterestSelection:
    interest: InterestUpdate
    utility: float


class InterestEngine:
    """Selects at most one non-intrusive self-project carryover."""

    def select(self, query: str, interests: Iterable[InterestUpdate]) -> InterestSelection | None:
        candidates: list[InterestSelection] = []
        for interest in interests:
            if interest.status != "active":
                continue
            relevance = lexical_overlap(
                query, f"{interest.title} {interest.why} {interest.next_action or ''}"
            )
            next_action_bonus = 0.12 if interest.next_action else 0.0
            utility = 0.55 * interest.priority + 0.33 * relevance + next_action_bonus
            candidates.append(InterestSelection(interest=interest, utility=min(1.0, utility)))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.utility, reverse=True)
        return candidates[0] if candidates[0].utility >= 0.42 else None

    @staticmethod
    def decayed_priority(priority: float, days_inactive: float, *, half_life_days: float = 120.0) -> float:
        return max(
            0.0, min(1.0, priority * math.exp(-math.log(2) * max(0.0, days_inactive) / half_life_days))
        )

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
