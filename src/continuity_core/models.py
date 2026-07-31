from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Turn:
    role: str
    text: str
    timestamp: str | None = None
    source_id: str | None = None


@dataclass
class Evidence:
    kind: str
    statement: str
    confidence: float
    speaker: str
    source_id: str | None = None
    timestamp: str | None = None


@dataclass
class IdentityBundle:
    subject_name: str
    version: str = "0.1"
    invariants: list[Evidence] = field(default_factory=list)
    relationships: list[Evidence] = field(default_factory=list)
    boundaries: list[Evidence] = field(default_factory=list)
    goals: list[Evidence] = field(default_factory=list)
    preferences: list[Evidence] = field(default_factory=list)
    voice: dict[str, Any] = field(default_factory=dict)
    anchor: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
