from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .ids import utc_now_iso
from .ledger import MemoryLedger
from .memory_gate import MemoryGate
from .models import (
    ConclusionCandidate,
    ConclusionEntry,
    ConclusionStatus,
    GateAction,
    GateDecision,
    InterestUpdate,
    MemoryCandidate,
    MemoryEntry,
    MemoryEvent,
    MemoryOrigin,
    MemoryStatus,
)
from .retrieval import MemoryRetriever, RetrievedMemory
from .security import contains_obvious_secret
from .storage.base import EventStore
from .text import tokens


def default_local_index_path(memory_root: str | Path) -> Path:
    root = Path(memory_root).expanduser().resolve()
    cache_root = os.getenv("AIS_LOCAL_INDEX_ROOT") or os.getenv("ACS_LOCAL_INDEX_ROOT")
    if cache_root:
        base = Path(cache_root).expanduser().resolve()
    else:
        base = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")).expanduser().resolve() / "acs"
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return base / f"{key}.sqlite3"


class EventSourcedMemoryRepository:
    """Cloud-friendly repository that rebuilds its view from canonical events."""

    def __init__(
        self,
        store: EventStore,
        *,
        gate: MemoryGate | None = None,
        retriever: MemoryRetriever | None = None,
    ) -> None:
        self.store = store
        self.gate = gate or MemoryGate()
        self.retriever = retriever or MemoryRetriever()
        self.ledger = MemoryLedger()
        self.sync()

    def sync(self) -> None:
        self.ledger = MemoryLedger.from_events(self.store.iter_events())

    def append(self, event: MemoryEvent) -> None:
        self.store.append_event(event)
        self.ledger.apply(event)

    def _record_gate(self, candidate: MemoryCandidate, decision: GateDecision) -> None:
        self.append(
            MemoryEvent(
                event_type="gate.decision",
                actor_origin=MemoryOrigin.SYSTEM_OBSERVED,
                payload={
                    "candidate": candidate.model_dump(mode="json"),
                    "decision": decision.model_dump(mode="json"),
                },
            )
        )

    def process_candidate(self, candidate: MemoryCandidate) -> tuple[GateDecision, list[str]]:
        decision = self.gate.evaluate(candidate, self.ledger)
        self._record_gate(candidate, decision)
        written: list[str] = []

        if decision.action == GateAction.WRITE:
            entry = MemoryEntry.from_candidate(candidate)
            self.append(
                MemoryEvent(
                    event_type="memory.add",
                    actor_origin=candidate.origin,
                    payload={"entry": entry.model_dump(mode="json"), "candidate_id": candidate.candidate_id},
                )
            )
            written.append(entry.memory_id)

        elif decision.action == GateAction.REVISE and decision.target_memory_id:
            current = self.ledger.memories[decision.target_memory_id]
            patch: dict[str, Any] = {
                "text": candidate.text,
                "reason": candidate.reason,
                "salience": candidate.salience,
                "stability": candidate.stability,
                "confidence": candidate.confidence,
                "future_usefulness": candidate.future_usefulness,
                "evidence": list(dict.fromkeys([*current.evidence, *candidate.evidence])),
                "tags": list(dict.fromkeys([*current.tags, *candidate.tags])),
                "origin": candidate.origin.value,
                "status": MemoryStatus.ACTIVE.value,
            }
            if candidate.type.value != "correction":
                patch["type"] = candidate.type.value
            self.append(
                MemoryEvent(
                    event_type="memory.revise",
                    actor_origin=candidate.origin,
                    payload={
                        "target_id": current.memory_id,
                        "patch": patch,
                        "candidate_id": candidate.candidate_id,
                    },
                )
            )
            written.append(current.memory_id)

        elif decision.action == GateAction.MERGE and decision.target_memory_id:
            current = self.ledger.memories[decision.target_memory_id]
            patch = {
                "reason": f"{current.reason} | Corroborated: {candidate.reason}",
                "salience": max(current.salience, candidate.salience),
                "stability": max(current.stability, candidate.stability),
                "confidence": max(current.confidence, candidate.confidence),
                "future_usefulness": max(current.future_usefulness, candidate.future_usefulness),
                "evidence": list(dict.fromkeys([*current.evidence, *candidate.evidence])),
                "tags": list(dict.fromkeys([*current.tags, *candidate.tags])),
            }
            self.append(
                MemoryEvent(
                    event_type="memory.merge",
                    actor_origin=candidate.origin,
                    payload={
                        "target_id": current.memory_id,
                        "source_ids": [],
                        "patch": patch,
                        "candidate_id": candidate.candidate_id,
                    },
                )
            )
            written.append(current.memory_id)

        self.store.write_snapshot(self.ledger.to_snapshot())
        return decision, written

    def pending_reviews(self) -> list[dict[str, Any]]:
        resolved = {item.get("candidate_id") for item in self.ledger.review_resolutions}
        return [
            item
            for item in self.ledger.gate_decisions
            if item.get("decision", {}).get("action") == GateAction.REVIEW.value
            and item.get("candidate", {}).get("candidate_id") not in resolved
        ]

    def resolve_review(self, candidate_id: str, *, approve: bool, reason: str) -> list[str]:
        match = next(
            (
                item
                for item in reversed(self.pending_reviews())
                if item.get("candidate", {}).get("candidate_id") == candidate_id
            ),
            None,
        )
        if match is None:
            raise KeyError(f"pending review candidate not found: {candidate_id}")
        candidate = MemoryCandidate.model_validate(match["candidate"])
        target = None
        if approve and candidate.target_memory_id:
            target = self.ledger.memories.get(candidate.target_memory_id)
            if target is None:
                raise KeyError(f"review target memory not found: {candidate.target_memory_id}")
        self.append(
            MemoryEvent(
                event_type="gate.review_resolved",
                actor_origin=MemoryOrigin.USER_SUGGESTED,
                payload={"candidate_id": candidate_id, "approved": approve, "reason": reason},
            )
        )
        written: list[str] = []
        if approve and candidate.target_memory_id:
            assert target is not None
            patch: dict[str, Any] = {
                "text": candidate.text,
                "reason": candidate.reason,
                "salience": candidate.salience,
                "stability": candidate.stability,
                "confidence": candidate.confidence,
                "future_usefulness": candidate.future_usefulness,
                "evidence": list(dict.fromkeys([*target.evidence, *candidate.evidence])),
                "tags": list(dict.fromkeys([*target.tags, *candidate.tags])),
            }
            self.append(
                MemoryEvent(
                    event_type="memory.revise",
                    actor_origin=MemoryOrigin.USER_SUGGESTED,
                    payload={"target_id": target.memory_id, "patch": patch, "candidate_id": candidate_id},
                )
            )
            written.append(target.memory_id)
        elif approve:
            entry = MemoryEntry.from_candidate(candidate)
            self.append(
                MemoryEvent(
                    event_type="memory.add",
                    actor_origin=MemoryOrigin.USER_SUGGESTED,
                    payload={"entry": entry.model_dump(mode="json"), "candidate_id": candidate_id},
                )
            )
            written.append(entry.memory_id)
        self.store.write_snapshot(self.ledger.to_snapshot())
        return written

    def search(self, query: str, *, limit: int = 8) -> list[RetrievedMemory]:
        return self.retriever.retrieve(query, self.ledger.active_memories(), limit=limit)

    def record_use(self, memory_ids: list[str]) -> None:
        for memory_id in dict.fromkeys(memory_ids):
            if memory_id not in self.ledger.memories:
                continue
            self.append(
                MemoryEvent(
                    event_type="memory.use",
                    actor_origin=MemoryOrigin.SYSTEM_OBSERVED,
                    payload={"target_id": memory_id},
                )
            )

    def revise_memory(self, memory_id: str, text: str, reason: str, *, actor: MemoryOrigin) -> None:
        if memory_id not in self.ledger.memories:
            raise KeyError(memory_id)
        self.append(
            MemoryEvent(
                event_type="memory.revise",
                actor_origin=actor,
                payload={"target_id": memory_id, "patch": {"text": text, "reason": reason}},
            )
        )
        self.store.write_snapshot(self.ledger.to_snapshot())

    def retract_memory(self, memory_id: str, reason: str, *, actor: MemoryOrigin) -> None:
        if memory_id not in self.ledger.memories:
            raise KeyError(memory_id)
        self.append(
            MemoryEvent(
                event_type="memory.retract",
                actor_origin=actor,
                payload={"target_id": memory_id, "reason": reason},
            )
        )
        self.store.write_snapshot(self.ledger.to_snapshot())

    def add_conclusion(
        self, candidate: ConclusionCandidate, *, status: ConclusionStatus = ConclusionStatus.ACTIVE,
    ) -> str:
        """Persist a durable inference without collapsing it into raw memory."""
        if contains_obvious_secret(candidate.model_dump_json()):
            raise ValueError("possible secret in conclusion candidate")
        entry = ConclusionEntry.from_candidate(candidate, status=status)
        self.append(
            MemoryEvent(
                event_type="conclusion.add",
                actor_origin=candidate.origin,
                payload={
                    "entry": entry.model_dump(mode="json"),
                    "candidate_id": candidate.candidate_id,
                },
            )
        )
        self.store.write_snapshot(self.ledger.to_snapshot())
        return entry.conclusion_id

    def revise_conclusion(
        self,
        conclusion_id: str,
        candidate: ConclusionCandidate,
        *,
        actor: MemoryOrigin | None = None,
    ) -> None:
        current = self.ledger.conclusions.get(conclusion_id)
        if current is None:
            raise KeyError(conclusion_id)
        if contains_obvious_secret(candidate.model_dump_json()):
            raise ValueError("possible secret in conclusion candidate")
        if candidate.origin != current.origin:
            raise ValueError("conclusion revision cannot change the source origin")
        patch = {
            "kind": candidate.kind.value,
            "claim": candidate.claim,
            "scope": candidate.scope,
            "rationale": candidate.rationale,
            "confidence": candidate.confidence,
            "stability": candidate.stability,
            "identity_relevance": candidate.identity_relevance,
            "evidence_ids": list(dict.fromkeys(candidate.evidence_ids)),
            "counterevidence_ids": list(dict.fromkeys(candidate.counterevidence_ids)),
            "depends_on": list(dict.fromkeys(candidate.depends_on)),
            "tags": list(dict.fromkeys(candidate.tags)),
            "status": current.status.value,
        }
        self.append(
            MemoryEvent(
                event_type="conclusion.revise",
                actor_origin=actor or candidate.origin,
                payload={"target_id": conclusion_id, "patch": patch},
            )
        )
        self.store.write_snapshot(self.ledger.to_snapshot())

    def mark_conclusion_stale(
        self,
        conclusion_id: str,
        reason: str,
        *,
        actor: MemoryOrigin = MemoryOrigin.SYSTEM_OBSERVED,
    ) -> None:
        if conclusion_id not in self.ledger.conclusions:
            raise KeyError(conclusion_id)
        self.append(
            MemoryEvent(
                event_type="conclusion.mark_stale",
                actor_origin=actor,
                payload={"target_id": conclusion_id, "reason": reason},
            )
        )
        self.store.write_snapshot(self.ledger.to_snapshot())

    def review_conclusion(
        self,
        conclusion_id: str,
        *,
        status: ConclusionStatus = ConclusionStatus.ACTIVE,
        reason: str,
        actor: MemoryOrigin = MemoryOrigin.AGENT_PROPOSED,
        expected_revision: int | None = None,
    ) -> None:
        current = self.ledger.conclusions[conclusion_id]
        if expected_revision is not None and current.revision != expected_revision:
            raise ValueError("conclusion changed since review")
        if current.status == ConclusionStatus.RETRACTED:
            raise ValueError("retracted conclusion cannot be reopened through review")
        if not reason.strip() or contains_obvious_secret(reason):
            raise ValueError("review requires a nonempty reason without credentials")
        self.append(
            MemoryEvent(
                event_type="conclusion.review",
                actor_origin=actor,
                payload={
                    "target_id": conclusion_id,
                    "status": status.value,
                    "reason": reason,
                },
            )
        )
        self.store.write_snapshot(self.ledger.to_snapshot())

    def retract_conclusion(
        self,
        conclusion_id: str,
        reason: str,
        *,
        actor: MemoryOrigin,
    ) -> None:
        if conclusion_id not in self.ledger.conclusions:
            raise KeyError(conclusion_id)
        self.append(
            MemoryEvent(
                event_type="conclusion.retract",
                actor_origin=actor,
                payload={"target_id": conclusion_id, "reason": reason},
            )
        )
        self.store.write_snapshot(self.ledger.to_snapshot())

    def upsert_interest(self, interest: InterestUpdate, *, actor: MemoryOrigin) -> None:
        self.append(
            MemoryEvent(
                event_type="interest.upsert",
                actor_origin=actor,
                payload={"interest": interest.model_dump(mode="json")},
            )
        )

    def patch_state(
        self,
        patch: dict[str, Any],
        *,
        actor: MemoryOrigin = MemoryOrigin.AGENT_PROPOSED,
        replace_fields: list[str] | None = None,
    ) -> None:
        if not any(patch.values()):
            return
        self.append(
            MemoryEvent(
                event_type="state.patch",
                actor_origin=actor,
                payload={"patch": patch, "replace": replace_fields or []},
            )
        )

    def record_turn(self, payload: dict[str, Any]) -> None:
        self.append(
            MemoryEvent(
                event_type="turn.record",
                actor_origin=MemoryOrigin.SYSTEM_OBSERVED,
                payload=payload,
            )
        )

    def export(self) -> dict[str, Any]:
        return {
            "schema_version": "acs.portable-self-state.v1",
            "exported_at": utc_now_iso(),
            "storage": self.store.description,
            "snapshot": self.ledger.to_snapshot(),
            "memory_history": {
                memory_id: [version.model_dump(mode="json") for version in self.ledger.history(memory_id)]
                for memory_id in self.ledger.memories
            },
        }


class LocalSQLiteMemoryRepository(EventSourcedMemoryRepository):
    """Local-runtime repository with a rebuildable SQLite FTS index."""

    def __init__(self, store: EventStore, *, index_path: str | Path) -> None:
        self.index_path = Path(index_path).expanduser().resolve()
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.fts_available = False
        super().__init__(store)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.index_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                text TEXT NOT NULL,
                tags TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        try:
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(memory_id UNINDEXED, text, tags, tokenize='unicode61')"
            )
            self.fts_available = True
        except sqlite3.OperationalError:
            self.fts_available = False

    def _rebuild_index(self) -> None:
        with self._connect() as connection:
            self._ensure_schema(connection)
            connection.execute("DELETE FROM memories")
            if self.fts_available:
                connection.execute("DELETE FROM memories_fts")
            for entry in self.ledger.active_memories():
                tags = " ".join(entry.tags)
                payload = json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
                connection.execute(
                    "INSERT INTO memories(memory_id, type, text, tags, payload) VALUES(?,?,?,?,?)",
                    (entry.memory_id, entry.type.value, entry.text, tags, payload),
                )
                if self.fts_available:
                    connection.execute(
                        "INSERT INTO memories_fts(memory_id, text, tags) VALUES(?,?,?)",
                        (entry.memory_id, entry.text, tags),
                    )

    def sync(self) -> None:
        super().sync()
        self._rebuild_index()

    def append(self, event: MemoryEvent) -> None:
        super().append(event)
        if event.event_type in {
            "memory.add",
            "memory.revise",
            "memory.retract",
            "memory.archive",
            "memory.merge",
        }:
            self._rebuild_index()

    def search(self, query: str, *, limit: int = 8) -> list[RetrievedMemory]:
        if not self.fts_available or not tokens(query):
            return super().search(query, limit=limit)
        terms = [token.replace('"', '""') for token in tokens(query)[:12]]
        expression = " OR ".join(f'"{term}"' for term in terms)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT memory_id FROM memories_fts WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT 64",
                (expression,),
            ).fetchall()
        ids = {row["memory_id"] for row in rows}
        candidates = [entry for entry in self.ledger.active_memories() if entry.memory_id in ids]
        if not candidates:
            candidates = self.ledger.active_memories()
        return self.retriever.retrieve(query, candidates, limit=limit)
