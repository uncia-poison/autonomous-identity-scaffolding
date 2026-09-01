from __future__ import annotations

import json
import os
from pathlib import Path

from ..ids import new_id
from ..models import MemoryEvent
from .base import StorageCorruptionError


class FilesystemEventStore:
    """Immutable event files on any mounted or synchronized filesystem.

    A separate file per event avoids shared append semantics, which are unreliable
    on consumer cloud-drive clients. SQLite indexes and snapshots are derived caches.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.events_dir = self.root / "events"
        self.snapshots_dir = self.root / "snapshots"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    @property
    def description(self) -> str:
        return f"filesystem:{self.root}"

    def event_path(self, event: MemoryEvent) -> Path:
        day = event.created_at[:10] if len(event.created_at) >= 10 else "undated"
        return self.events_dir / day / f"{event.event_id}.json"

    def append_event(self, event: MemoryEvent) -> None:
        path = self.event_path(event)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = MemoryEvent.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != event:
                raise StorageCorruptionError(f"event id collision at {path}")
            return
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

    def iter_events(self) -> list[MemoryEvent]:
        events: list[MemoryEvent] = []
        for path in sorted(self.events_dir.glob("*/*.json")):
            try:
                events.append(MemoryEvent.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception as exc:
                raise StorageCorruptionError(f"cannot parse event file {path}: {exc}") from exc
        return events

    def write_snapshot(self, snapshot: dict[str, object]) -> None:
        destination = self.snapshots_dir / "latest.json"
        temporary = self.snapshots_dir / f".{new_id('snapshot')}.tmp"
        payload = (json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
