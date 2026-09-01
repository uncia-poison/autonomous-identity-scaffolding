from __future__ import annotations

import math
import re
from datetime import datetime, timezone

TOKEN_RE = re.compile(r"[\wЁёА-Яа-я'-]{2,}", re.UNICODE)
STOPWORDS = {
    "and",
    "the",
    "that",
    "this",
    "with",
    "from",
    "have",
    "your",
    "you",
    "are",
    "for",
    "это",
    "как",
    "что",
    "для",
    "его",
    "она",
    "они",
    "или",
    "мне",
    "тебя",
    "тебе",
    "меня",
}


def tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text) if token.casefold() not in STOPWORDS]


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def normalized_text(text: str) -> str:
    return " ".join(tokens(text))


def jaccard(left: str, right: str) -> float:
    a, b = token_set(left), token_set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def lexical_overlap(query: str, text: str) -> float:
    q, t = token_set(query), token_set(text)
    if not q or not t:
        return 0.0
    return len(q & t) / math.sqrt(len(q) * len(t))


def recency_score(timestamp: str | None, *, half_life_days: float = 90.0) -> float:
    if not timestamp:
        return 0.0
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.0
    age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400)
    return math.exp(-math.log(2) * age_days / half_life_days)
