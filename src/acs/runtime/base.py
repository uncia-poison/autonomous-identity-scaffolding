from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..clients.base import ModelClient
from ..ids import new_id, utc_now_iso
from ..metrics import memory_metrics, response_metrics
from ..models import (
    CharacterGenome,
    MemoryCandidate,
    MemoryOrigin,
    MemoryType,
    ReflectionBatch,
    SelfState,
    TurnOutcome,
)
from ..prompts import build_reflection_messages, build_response_messages
from ..repository import EventSourcedMemoryRepository
from ..security import redact_for_storage
from ..stance import StanceEngine


def _merge_self_state(base: SelfState, patch: dict[str, object]) -> SelfState:
    data = base.model_dump(mode="json")
    allowed = set(SelfState.model_fields)
    for key, value in patch.items():
        if key in allowed:
            data[key] = value
    return SelfState.model_validate(data)


def _sanitize_reflection(batch: ReflectionBatch) -> ReflectionBatch:
    """Prevent a model-only reflection pass from claiming privileged provenance."""

    candidates = []
    for candidate in batch.memory_candidates:
        if candidate.origin in {MemoryOrigin.AGENT_PROPOSED, MemoryOrigin.USER_SUGGESTED}:
            candidates.append(candidate)
            continue
        candidates.append(
            candidate.model_copy(
                update={
                    "origin": MemoryOrigin.AGENT_PROPOSED,
                    "reason": (candidate.reason + " [runtime normalized unverifiable provenance]")[:2000],
                    "tags": list(
                        dict.fromkeys(
                            [
                                *candidate.tags,
                                "runtime:unverified-provenance",
                                f"claimed-origin:{candidate.origin.value}",
                            ]
                        )
                    )[:20],
                }
            )
        )
    interests = []
    for interest in batch.interest_updates:
        if interest.origin in {"agent_selected", "user_suggested"}:
            interests.append(interest)
        else:
            interests.append(
                interest.model_copy(
                    update={
                        "origin": "agent_selected",
                        "why": (interest.why + " [runtime normalized unverifiable archive provenance]")[
                            :1000
                        ],
                    }
                )
            )
    return batch.model_copy(update={"memory_candidates": candidates, "interest_updates": interests})


@dataclass
class CharacterRuntime:
    client: ModelClient
    repository: EventSourcedMemoryRepository
    genome: CharacterGenome
    base_self_state: SelfState
    runtime_variant: Literal["local", "api", "test"]
    recall_limit: int = 8
    sync_before_turn: bool = True
    tolerate_reflection_errors: bool = True

    @property
    def self_state(self) -> SelfState:
        return _merge_self_state(self.base_self_state, self.repository.ledger.state)

    def turn(self, user_message: str, *, session_id: str = "default") -> TurnOutcome:
        if not user_message.strip():
            raise ValueError("user_message cannot be empty")
        if self.sync_before_turn:
            self.repository.sync()

        state_before = self.self_state
        recalled = self.repository.search(user_message, limit=self.recall_limit)
        stance = StanceEngine().select(user_message, self.genome)
        response_messages = build_response_messages(
            user_message=user_message,
            genome=self.genome,
            self_state=state_before,
            ledger=self.repository.ledger,
            recalled=recalled,
            stance=stance,
            recent_turns=self.repository.ledger.recent_turns(limit=6, session_id=session_id),
        )
        response = self.client.generate(response_messages).strip()
        if not response:
            raise RuntimeError("model returned an empty response")

        drift_alerts: list[str] = []
        try:
            reflection = self.client.reflect(
                build_reflection_messages(
                    user_message=user_message,
                    response=response,
                    genome=self.genome,
                    self_state=state_before,
                    recalled=recalled,
                )
            )
            reflection = _sanitize_reflection(reflection)
        except Exception as exc:
            if not self.tolerate_reflection_errors:
                raise
            reflection = ReflectionBatch(
                drift_alerts=[f"reflection_error:{type(exc).__name__}"],
                response_assessment="Reflection failed; the visible response was retained without model-proposed memory writes.",
            )
        drift_alerts.extend(reflection.drift_alerts)

        decisions = []
        written: list[str] = []
        for candidate in reflection.memory_candidates:
            decision, candidate_writes = self.repository.process_candidate(candidate)
            decisions.append(decision)
            written.extend(candidate_writes)
        for interest in reflection.interest_updates:
            actor = (
                MemoryOrigin.USER_SUGGESTED
                if interest.origin == "user_suggested"
                else MemoryOrigin.AGENT_PROPOSED
            )
            interest_candidate = MemoryCandidate(
                type=MemoryType.SELF_INTEREST,
                text=f"{interest.title}: {interest.why}",
                origin=actor,
                reason=f"Proposed self-project with status {interest.status}.",
                salience=interest.priority,
                stability=0.68 if interest.status == "active" else 0.56,
                confidence=0.68,
                user_imposition_risk=0.15 if actor == MemoryOrigin.AGENT_PROPOSED else 0.65,
                future_usefulness=max(0.55, interest.priority),
                tags=["self-project", f"interest:{interest.interest_id}"],
            )
            decision, interest_writes = self.repository.process_candidate(interest_candidate)
            decisions.append(decision)
            written.extend(interest_writes)
            if interest_writes:
                self.repository.upsert_interest(interest, actor=actor)

        recalled_ids = [result.entry.memory_id for result in recalled]
        self.repository.record_use(recalled_ids)
        now = utc_now_iso()
        requested_state = reflection.self_state_patch
        if requested_state.current_goals or requested_state.recent_lessons:
            drift_alerts.append("ungated_self_state_fields_derived_from_memory")
        active = self.repository.ledger.active_memories()
        goals = [entry.text for entry in active if entry.type == MemoryType.SELF_GOAL][-10:]
        lessons = [
            entry.text
            for entry in sorted(active, key=lambda item: item.updated_at, reverse=True)
            if entry.type in {MemoryType.BELIEF, MemoryType.REGRET, MemoryType.CORRECTION}
        ][:10]
        state_patch = {
            "current_goals": goals,
            "active_doubts": requested_state.active_doubts,
            "recent_lessons": lessons,
            "open_questions": requested_state.open_questions,
        }
        state_patch.update(
            {
                "last_turn_at": now,
                "last_memory_write_ids": list(dict.fromkeys(written)),
            }
        )
        state_patch["drift_alerts"] = drift_alerts
        self.repository.patch_state(
            state_patch,
            replace_fields=["current_goals", "recent_lessons", "last_memory_write_ids", "drift_alerts"],
        )

        turn_id = new_id("turn")
        turn_metrics = response_metrics(response, stance)
        self.repository.record_turn(
            {
                "turn_id": turn_id,
                "session_id": session_id,
                "user_message": redact_for_storage(user_message),
                "response": redact_for_storage(response),
                "stance": stance.model_dump(mode="json"),
                "recalled_memory_ids": recalled_ids,
                "gate_decisions": [decision.model_dump(mode="json") for decision in decisions],
                "written_memory_ids": list(dict.fromkeys(written)),
                "drift_alerts": drift_alerts,
                "reflection_assessment": reflection.response_assessment,
                "metrics": {**turn_metrics, **memory_metrics(self.repository.ledger)},
                "runtime_variant": self.runtime_variant,
                "model": self.client.model_name,
                "created_at": now,
            }
        )
        self.repository.store.write_snapshot(self.repository.ledger.to_snapshot())
        return TurnOutcome(
            turn_id=turn_id,
            session_id=session_id,
            response=response,
            stance=stance,
            recalled_memory_ids=recalled_ids,
            gate_decisions=decisions,
            written_memory_ids=list(dict.fromkeys(written)),
            drift_alerts=drift_alerts,
            runtime_variant=self.runtime_variant,
            model=self.client.model_name,
            created_at=now,
        )
