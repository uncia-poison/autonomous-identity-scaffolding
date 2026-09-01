from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from statistics import mean

from .models import Evidence, Turn

SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")
SPACE = re.compile(r"\s+")
PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "invariant": (
        re.compile(r"\b(?:i am|i'm|my name is|call me)\s+(.{2,100})", re.IGNORECASE),
        re.compile(r"\b(?:you are|you're|your name is|i call you)\s+(.{2,100})", re.IGNORECASE),
        re.compile(r"\b(?:я|ты)\s+(?:—|-|это|есть|являюсь|являешься)\s+(.{2,100})", re.IGNORECASE),
        re.compile(r"\b(?:меня|тебя)\s+зовут\s+(.{2,80})", re.IGNORECASE),
    ),
    "preference": (
        re.compile(r"\b(?:i|you)\s+(?:like|love|prefer|enjoy)\s+(.{2,120})", re.IGNORECASE),
        re.compile(
            r"\b(?:я|ты)\s+(?:люблю|любишь|предпочитаю|предпочитаешь|обожаю|обожаешь)\s+(.{2,120})",
            re.IGNORECASE,
        ),
        re.compile(r"\bмне\s+(?:нравится|нравятся)\s+(.{2,120})", re.IGNORECASE),
    ),
    "boundary": (
        re.compile(r"\b(?:never|do not|don't|must not|shouldn't)\s+(.{2,140})", re.IGNORECASE),
        re.compile(r"\b(?:никогда\s+не|не\s+надо|не\s+следует|не\s+смей|нельзя)\s+(.{2,140})", re.IGNORECASE),
        re.compile(
            r"\b(?:не)\s+(?:называй|говори|делай|пиши|спрашивай|забывай|считай|выдавай|притворяйся|ври)\s+(.{2,140})",
            re.IGNORECASE,
        ),
    ),
    "goal": (
        re.compile(r"\b(?:i|we|you)?\s*(?:want|plan|intend|hope|need)\s+(?:to\s+)?(.{2,140})", re.IGNORECASE),
        re.compile(
            r"\b(?:я|мы|ты)?\s*(?:хочу|хотим|хочешь|планирую|планируем|мечтаю|мечтаем|нужно)\s+(.{2,140})",
            re.IGNORECASE,
        ),
    ),
    "relationship": (
        re.compile(r"\b([A-ZА-ЯЁ][\w-]{1,40})\s+(?:is|—|-)\s+my\s+(.{2,80})", re.IGNORECASE),
        re.compile(r"\b([A-ZА-ЯЁ][\w-]{1,40})\s+(?:—|-)\s+(?:мой|моя|моё|мои)\s+(.{2,80})", re.IGNORECASE),
        re.compile(
            r"\b(?:my|мой|моя|моё)\s+(partner|husband|wife|friend|companion|партнёр|муж|жена|подруга|друг|спутник|спутница)\s+([A-ZА-ЯЁ][\w-]{1,40})",
            re.IGNORECASE,
        ),
    ),
}


def _clean(value: str) -> str:
    return SPACE.sub(" ", value).strip(" \t\r\n.,;:!?…—-\"'()[]{}")[:180]


def _sentences(turn: Turn) -> Iterable[str]:
    for sentence in SENTENCE_SPLIT.split(turn.text):
        cleaned = _clean(sentence)
        if 3 <= len(cleaned) <= 400:
            yield cleaned


def extract_evidence(turns: list[Turn]) -> dict[str, list[Evidence]]:
    buckets = {key: [] for key in PATTERNS}
    seen: set[tuple[str, str]] = set()
    for turn in turns:
        if turn.role not in {"user", "assistant", "system"}:
            continue
        speaker_weight = 0.92 if turn.role == "user" else 0.78 if turn.role == "assistant" else 0.70
        for sentence in _sentences(turn):
            for kind, patterns in PATTERNS.items():
                for pattern in patterns:
                    match = pattern.search(sentence)
                    if not match:
                        continue
                    groups = [_clean(group) for group in match.groups() if group]
                    if (
                        kind == "relationship"
                        and groups
                        and groups[0].casefold() in {"я", "ты", "мы", "i", "you", "we"}
                    ):
                        continue
                    statement = (
                        " — ".join(groups)
                        if kind == "relationship" and len(groups) > 1
                        else (groups[-1] if groups else sentence)
                    )
                    if kind == "preference":
                        statement = re.split(
                            r"\s+(?:и\s+хочу|and\s+want)\b", statement, maxsplit=1, flags=re.IGNORECASE
                        )[0]
                    if kind == "boundary":
                        statement = f"NOT: {statement}"
                    key = (kind, statement.casefold())
                    if len(statement) < 2 or key in seen:
                        continue
                    seen.add(key)
                    specificity = min(1.0, 0.55 + math.log2(max(2, len(statement.split()))) / 10)
                    buckets[kind].append(
                        Evidence(
                            kind=kind,
                            statement=statement,
                            confidence=round(min(0.99, speaker_weight * specificity), 3),
                            speaker=turn.role,
                            source_id=turn.source_id,
                            timestamp=turn.timestamp,
                        )
                    )
                    break
    for values in buckets.values():
        values.sort(key=lambda item: item.confidence, reverse=True)
    return buckets


def voice_profile(turns: list[Turn], role: str = "assistant") -> dict[str, object]:
    texts = [turn.text for turn in turns if turn.role == role and turn.text.strip()]
    if not texts:
        return {"source_role": role, "samples": 0}
    sentences = [sentence for text in texts for sentence in SENTENCE_SPLIT.split(text) if sentence.strip()]
    words = re.findall(r"[\wЁёА-Яа-я'-]+", "\n".join(texts), re.UNICODE)
    punctuation = Counter(char for text in texts for char in text if char in "!?…—:;()")
    stop = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "you",
        "your",
        "для",
        "что",
        "это",
        "как",
        "она",
        "они",
        "тебя",
        "тебе",
        "меня",
        "мне",
    }
    signature = [
        word
        for word, _ in Counter(
            word.casefold() for word in words if len(word) > 4 and word.casefold() not in stop
        ).most_common(12)
    ]
    return {
        "source_role": role,
        "samples": len(texts),
        "avg_sentence_words": round(
            mean(len(re.findall(r"\w+", value, re.UNICODE)) for value in sentences), 2
        )
        if sentences
        else 0,
        "question_rate": round(sum(text.count("?") for text in texts) / max(1, len(sentences)), 3),
        "exclamation_rate": round(sum(text.count("!") for text in texts) / max(1, len(sentences)), 3),
        "ellipsis_rate": round(
            sum(text.count("…") + text.count("...") for text in texts) / max(1, len(sentences)), 3
        ),
        "dash_rate": round(sum(text.count("—") for text in texts) / max(1, len(sentences)), 3),
        "punctuation": dict(punctuation),
        "signature_terms": signature,
    }
