from __future__ import annotations

import hashlib

from .ledger import MemoryLedger
from .models import CharacterGenome, MemoryType


def _slug(text: str, width: int = 8) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:width]


def compile_character_anchor(genome: CharacterGenome, ledger: MemoryLedger, *, max_items: int = 16) -> str:
    """Create a debuggable KAiScriptor-inspired portable anchor.

    The anchor is an export representation. It has no hidden persistence and must
    be explicitly re-presented to a model in a later session.
    """

    parts = [f"α[{genome.display_name}|{genome.character_id}|v{genome.version}]"]
    values = sorted(genome.values.items(), key=lambda item: item[1], reverse=True)[:5]
    if values:
        parts.append("Ω{" + ";".join(f"{name}:{weight:.2f}" for name, weight in values) + "}")
    principles = [entry for entry in ledger.active_memories() if entry.type == MemoryType.SELF_PRINCIPLE]
    if principles:
        parts.append(
            "Θ{" + ";".join(f"P:{_slug(e.text)}={e.text}" for e in principles[: max_items // 2]) + "}"
        )
    interests = [entry for entry in ledger.active_memories() if entry.type == MemoryType.SELF_INTEREST]
    if interests or genome.interests:
        items = [entry.text for entry in interests] + genome.interests
        parts.append("Δ{" + ";".join(f"I:{_slug(text)}={text}" for text in items[:5]) + "}")
    if genome.vetoes:
        parts.append("∇{" + ";".join(genome.vetoes[:6]) + "}")
    return " ".join(parts)
