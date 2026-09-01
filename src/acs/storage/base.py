from __future__ import annotations

from typing import Protocol

from ..models import MemoryEvent


class StorageCorruptionError(RuntimeError):
    pass


class EventStore(Protocol):
    """Canonical immutable event storage used by ACS repositories."""

    def append_event(self, event: MemoryEvent) -> None: ...

    def iter_events(self) -> list[MemoryEvent]: ...

    def write_snapshot(self, snapshot: dict[str, object]) -> None: ...

    @property
    def description(self) -> str: ...
