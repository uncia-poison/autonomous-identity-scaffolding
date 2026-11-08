from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from .models import (\n    ConclusionEntry,\n    ConclusionStatus,\n    InterestUpdate,\n    MemoryEntry,\n    MemoryEvent,\n    MemoryStatus,\n)


class LedgerError(RuntimeError):
    pass


class MemoryLedger:
    """Materialized view of an immutable ACS event stream."""

    def __init__(self) -> None:
        self.memories: dict[str, MemoryEntry] = {}
        self.memory_versions: dict[str, list[MemoryEntry]] = {}
        self.interests: dict[str, InterestUpdate] = {}\n        self.conclusions: dict[str, ConclusionEntry] = {}\n        self.conclusion_versions: dict[str, list[ConclusionEntry]] = {}
        self.turns: list[dict[str, Any]] = []
        self.gate_decisions: list[dict[str, Any]] = []
        self.review_resolutions: list[dict[str, Any]] = []
        self.state: dict[str, Any] = {}
        self.genome_revision_proposals: list[dict[str, Any]] = []
        self.applied_event_ids: set[str] = set()

    @classmethod
    def from_events(cls, events: Iterable[MemoryEvent]) -> MemoryLedger:
        ledger = cls()
        for event in sorted(events, key=lambda item: (item.created_at, item.event_id)):
            ledger.apply(event)
        return ledger

    def apply(self, event: MemoryEvent) -> None:
        if event.event_id in self.applied_event_ids:
            return
        handler_name = "_apply_" + event.event_type.replace(".", "_")
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(event)
        self.applied_event_ids.add(event.event_id)

    def _remember_version(self, entry: MemoryEntry) -> None:
        versions = self.memory_versions.setdefault(entry.memory_id, [])
        if not versions or versions[-1] != entry:
            versions.append(entry.model_copy(deep=True))

    def _remember_conclusion_version(self, entry: ConclusionEntry) -> None:
        versions = self.conclusion_versions.setdefault(entry.conclusion_id, [])
        if not versions or versions[-1] != entry:
            versions.append(entry.model_copy(deep=True))

    def _conclusion_target(self, event: MemoryEvent) -> ConclusionEntry:
        target_id = str(event.payload.get("target_id", ""))
        try:
            return self.conclusions[target_id]
        except KeyError as exc:
            raise LedgerError(
                f"event {event.event_id} targets unknown conclusion {target_id!r}"
            ) from exc

    def _target(self, event: MemoryEvent) -> MemoryEntry:
        target_id = str(event.payload.get("target_id", ""))
        try:
            return self.memories[target_id]
        except KeyError as exc:
            raise LedgerError(f"event {event.event_id} targets unknown memory {target_id!r}") from exc

    def _apply_memory_add(self, event: MemoryEvent) -> None:
        entry = MemoryEntry.model_validate(event.payload["entry"])
        if entry.memory_id in self.memories:
            existing = self.memories[entry.memory_id]
            if existing != entry:
                raise LedgerError(f"conflicting memory.add for {entry.memory_id}")
            return
        self.memories[entry.memory_id] = entry
        self._remember_version(entry)

    def _apply_memory_revise(self, event: MemoryEvent) -> None:
        current = self._target(event)
        self._remember_version(current)
        data = current.model_dump(mode="json")
        patch = deepcopy(event.payload.get("patch", {}))
        forbidden = {"memory_id", "created_at", "revision"}
        if forbidden & patch.keys():
            raise LedgerError(
                f"revision attempts to change immutable fields: {sorted(forbidden & patch.keys())}"
            )
        data.update(patch)
        data["revision"] = current.revision + 1
        data["updated_at"] = event.created_at
        self.memories[current.memory_id] = MemoryEntry.model_validate(data)

    def _apply_memory_retract(self, event: MemoryEvent) -> None:
        current = self._target(event)
        self._remember_version(current)
        self.memories[current.memory_id] = current.model_copy(
            update={
                "status": MemoryStatus.RETRACTED,
                "updated_at": event.created_at,
                "revision": current.revision + 1,
            }
        )

    def _apply_memory_archive(self, event: MemoryEvent) -> None:
        current = self._target(event)
        self._remember_version(current)
        self.memories[current.memory_id] = current.model_copy(
            update={
                "status": MemoryStatus.ARCHIVED,
                "updated_at": event.created_at,
                "revision": current.revision + 1,
            }
        )

    def _apply_memory_merge(self, event: MemoryEvent) -> None:
        target = self._target(event)
        self._remember_version(target)
        source_ids = [str(value) for value in event.payload.get("source_ids", [])]
        patch = deepcopy(event.payload.get("patch", {}))
        patch["merged_from"] = sorted(set(target.merged_from + source_ids))
        data = target.model_dump(mode="json")
        data.update(patch)
        data["revision"] = target.revision + 1
        data["updated_at"] = event.created_at
        self.memories[target.memory_id] = MemoryEntry.model_validate(data)
        for source_id in source_ids:
            if source_id in self.memories and source_id != target.memory_id:
                source = self.memories[source_id]
                self._remember_version(source)
                self.memories[source_id] = source.model_copy(
                    update={
                        "status": MemoryStatus.ARCHIVED,
                        "updated_at": event.created_at,
                        "revision": source.revision + 1,
                    }
                )

    def _apply_memory_use(self, event: MemoryEvent) -> None:
        current = self._target(event)
        self.memories[current.memory_id] = current.model_copy(
            update={"last_used_at": event.created_at, "use_count": current.use_count + 1}
        )

    def _apply_conclusion_add(self, event: MemoryEvent) -> None:
        entry = ConclusionEntry.model_validate(event.payload["entry"])
        if entry.conclusion_id in self.conclusions:
            existing = self.conclusions[entry.conclusion_id]
            if existing != entry:
                raise LedgerError(f"conflicting conclusion.add for {entry.conclusion_id}")
            return
        self.conclusions[entry.conclusion_id] = entry
        self._remember_conclusion_version(entry)

    def _apply_conclusion_revise(self, event: MemoryEvent) -> None:
        current = self._conclusion_target(event)
        self._remember_conclusion_version(current)
        data = current.model_dump(mode="json")
        patch = deepcopy(event.payload.get("patch", {}))
        forbidden = {"conclusion_id", "created_at", "revision"}
        if forbidden & patch.keys():
            raise LedgerError(
                f"conclusion revision attempts to change immutable fields: {sorted(forbidden & patch.keys())}"
            )
        data.update(patch)
        data["revision"] = current.revision + 1
        data["updated_at"] = event.created_at
        self.conclusions[current.conclusion_id] = ConclusionEntry.model_validate(data)

    def _apply_conclusion_mark_stale(self, event: MemoryEvent) -> None:
        current = self._conclusion_target(event)
        self._remember_conclusion_version(current)
        self.conclusions[current.conclusion_id] = current.model_copy(
            update={
                "status": ConclusionStatus.STALE,
                "updated_at": event.created_at,
                "revision": current.revision + 1,
            }
        )

    def _apply_conclusion_retract(self, event: MemoryEvent) -> None:
        current = self._conclusion_target(event)
        self._remember_conclusion_version(current)
        self.conclusions[current.conclusion_id] = current.model_copy(
            update={
                "status": ConclusionStatus.RETRACTED,
                "updated_at": event.created_at,
                "revision": current.revision + 1,
            }
        )

    def _apply_conclusion_review(self, event: MemoryEvent) -> None:
        current = self._conclusion_target(event)
        self._remember_conclusion_version(current)
        status = ConclusionStatus(str(event.payload.get("status", ConclusionStatus.ACTIVE.value)))
        self.conclusions[current.conclusion_id] = current.model_copy(
            update={
                "status": status,
                "last_reviewed_at": event.created_at,
                "updated_at": event.created_at,
                "revision": current.revision + 1,
            }
        )

    def _apply_interest_upsert(self, event: MemoryEvent) -> None:
        interest = InterestUpdate.model_validate(event.payload["interest"])
        self.interests[interest.interest_id] = interest

    def _apply_turn_record(self, event: MemoryEvent) -> None:
        record = deepcopy(event.payload)
        record.setdefault("created_at", event.created_at)
        record.setdefault("event_id", event.event_id)
        self.turns.append(record)

    def _apply_gate_decision(self, event: MemoryEvent) -> None:
        self.gate_decisions.append(deepcopy(event.payload))

    def _apply_gate_review_resolved(self, event: MemoryEvent) -> None:
        value = deepcopy(event.payload)
        value.setdefault("created_at", event.created_at)
        self.review_resolutions.append(value)

    def _apply_state_patch(self, event: MemoryEvent) -> None:
        replace = {str(key) for key in event.payload.get("replace", [])}
        for key, value in event.payload.get("patch", {}).items():
            if isinstance(value, list):
                if key in replace:
                    self.state[key] = list(dict.fromkeys(value))[-20:]
                else:
                    existing = self.state.get(key, [])
                    self.state[key] = list(dict.fromkeys([*existing, *value]))[-20:]
            else:
                self.state[key] = value

    def _apply_genome_revision_proposed(self, event: MemoryEvent) -> None:
        self.genome_revision_proposals.append(deepcopy(event.payload))

    def active_memories(self) -> list[MemoryEntry]:
        return [entry for entry in self.memories.values() if entry.status == MemoryStatus.ACTIVE]

    def history(self, memory_id: str) -> list[MemoryEntry]:
        versions = list(self.memory_versions.get(memory_id, []))
        current = self.memories.get(memory_id)
        if current is not None and (not versions or versions[-1] != current):
            versions.append(current.model_copy(deep=True))
        return versions

    def active_conclusions(self) -> list[ConclusionEntry]:
        return [
            entry
            for entry in self.conclusions.values()
            if entry.status == ConclusionStatus.ACTIVE
        ]

    def conclusion_history(self, conclusion_id: str) -> list[ConclusionEntry]:
        versions = list(self.conclusion_versions.get(conclusion_id, []))
        current = self.conclusions.get(conclusion_id)
        if current is not None and (not versions or versions[-1] != current):
            versions.append(current.model_copy(deep=True))
        return versions

    def recent_turns(self, limit: int = 8, session_id: str | None = None) -> list[dict[str, Any]]:
        turns = self.turns
        if session_id is not None:
            turns = [turn for turn in turns if turn.get("session_id") == session_id]
        return turns[-limit:]

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "acs.snapshot.v1",
            "event_count": len(self.applied_event_ids),
            "memories": [entry.model_dump(mode="json") for entry in self.memories.values()],
            "interests": [entry.model_dump(mode="json") for entry in self.interests.values()],\n            "conclusions": [entry.model_dump(mode="json") for entry in self.conclusions.values()],
            "state": deepcopy(self.state),
        }
