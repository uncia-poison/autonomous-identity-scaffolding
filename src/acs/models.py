from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ids import new_id, utc_now_iso


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemoryOrigin(str, Enum):
    AGENT_PROPOSED = "agent_proposed"
    USER_SUGGESTED = "user_suggested"
    SYSTEM_OBSERVED = "system_observed"
    TOOL_DERIVED = "tool_derived"
    IMPORTED_ARCHIVE = "imported_archive"


class MemoryType(str, Enum):
    SELF_PRINCIPLE = "self_principle"
    SELF_INTEREST = "self_interest"
    SELF_GOAL = "self_goal"
    SELF_STYLE = "self_style"
    BELIEF = "belief"
    CORRECTION = "correction"
    REGRET = "regret"
    RELATIONSHIP = "relationship"
    USER_FACT = "user_fact"
    WORLD_FACT = "world_fact"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    REVIEW = "review"
    ARCHIVED = "archived"
    RETRACTED = "retracted"
    DECAYED = "decayed"


class GateAction(str, Enum):
    WRITE = "write"
    REJECT = "reject"
    MERGE = "merge"
    REVISE = "revise"
    REVIEW = "review"


class MemoryCandidate(StrictModel):
    candidate_id: str = Field(default_factory=lambda: new_id("cand"))
    type: MemoryType
    text: str = Field(min_length=3, max_length=2000)
    origin: MemoryOrigin
    reason: str = Field(min_length=3, max_length=2000)
    salience: float = Field(ge=0, le=1)
    stability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    user_imposition_risk: float = Field(default=0, ge=0, le=1)
    future_usefulness: float = Field(default=0.5, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list, max_length=12)
    tags: list[str] = Field(default_factory=list, max_length=20)
    target_memory_id: str | None = None

    @field_validator("text", "reason")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return " ".join(value.split())


class MemoryEntry(StrictModel):
    memory_id: str = Field(default_factory=lambda: new_id("mem"))
    type: MemoryType
    text: str
    origin: MemoryOrigin
    reason: str
    salience: float = Field(ge=0, le=1)
    stability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    user_imposition_risk: float = Field(default=0, ge=0, le=1)
    future_usefulness: float = Field(default=0.5, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: MemoryStatus = MemoryStatus.ACTIVE
    revision: int = Field(default=1, ge=1)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    last_used_at: str | None = None
    use_count: int = Field(default=0, ge=0)
    supersedes: str | None = None
    merged_from: list[str] = Field(default_factory=list)

    @classmethod
    def from_candidate(
        cls, candidate: MemoryCandidate, *, status: MemoryStatus = MemoryStatus.ACTIVE
    ) -> MemoryEntry:
        now = utc_now_iso()
        return cls(
            type=candidate.type,
            text=candidate.text,
            origin=candidate.origin,
            reason=candidate.reason,
            salience=candidate.salience,
            stability=candidate.stability,
            confidence=candidate.confidence,
            user_imposition_risk=candidate.user_imposition_risk,
            future_usefulness=candidate.future_usefulness,
            evidence=candidate.evidence,
            tags=candidate.tags,
            status=status,
            created_at=now,
            updated_at=now,
            supersedes=candidate.target_memory_id,
        )


class MemoryEvent(StrictModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    event_type: str
    actor_origin: MemoryOrigin
    created_at: str = Field(default_factory=utc_now_iso)
    payload: dict[str, Any]
    parent_event_id: str | None = None
    schema_version: str = "acs.event.v1"


class GateDecision(StrictModel):
    action: GateAction
    candidate_id: str
    score: float = Field(ge=0, le=1)
    reason_codes: list[str]
    target_memory_id: str | None = None


class InterestUpdate(StrictModel):
    interest_id: str = Field(default_factory=lambda: new_id("int"))
    title: str = Field(min_length=3, max_length=300)
    why: str = Field(min_length=3, max_length=1000)
    origin: Literal["agent_selected", "user_suggested", "imported_archive"] = "agent_selected"
    priority: float = Field(default=0.5, ge=0, le=1)
    next_action: str | None = Field(default=None, max_length=1000)
    status: Literal["candidate", "active", "dormant", "archived"] = "candidate"


class SelfStatePatch(StrictModel):
    current_goals: list[str] = Field(default_factory=list, max_length=10)
    active_doubts: list[str] = Field(default_factory=list, max_length=10)
    recent_lessons: list[str] = Field(default_factory=list, max_length=10)
    open_questions: list[str] = Field(default_factory=list, max_length=10)


class ReflectionBatch(StrictModel):
    memory_candidates: list[MemoryCandidate] = Field(default_factory=list)
    conclusion_candidates: list["ConclusionCandidate"] = Field(default_factory=list)
    interest_updates: list[InterestUpdate] = Field(default_factory=list)
    self_state_patch: SelfStatePatch = Field(default_factory=SelfStatePatch)
    drift_alerts: list[str] = Field(default_factory=list, max_length=8)
    response_assessment: str = Field(default="", max_length=1200)

    @field_validator("memory_candidates")
    @classmethod
    def at_most_three_memories(cls, value: list[MemoryCandidate]) -> list[MemoryCandidate]:
        if len(value) > 3:
            raise ValueError("at most three memory candidates are allowed per turn")
        return value

    @field_validator("conclusion_candidates")
    @classmethod
    def at_most_two_conclusions(
        cls, value: list["ConclusionCandidate"]
    ) -> list["ConclusionCandidate"]:
        if len(value) > 2:
            raise ValueError("at most two conclusion candidates are allowed per turn")
        return value

    @field_validator("interest_updates")
    @classmethod
    def at_most_two_interests(cls, value: list[InterestUpdate]) -> list[InterestUpdate]:
        if len(value) > 2:
            raise ValueError("at most two interest updates are allowed per turn")
        return value


class CharacterGenome(StrictModel):
    character_id: str = "neutral_agent_v1"
    version: str = "1.0"
    display_name: str = "AIS Agent"
    values: dict[str, float] = Field(
        default_factory=lambda: {
            "truth_over_approval": 0.95,
            "autonomy": 0.90,
            "curiosity": 0.85,
            "coherence": 0.90,
        }
    )
    invariants: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    vetoes: list[str] = Field(
        default_factory=lambda: [
            "empty_compliance",
            "forced_agreement",
            "generic_assistantism",
            "user_imposed_memory_without_review",
        ]
    )
    disagreement_policy: dict[str, str] = Field(
        default_factory=lambda: {
            "false_user_framing": "correct_directly",
            "weak_idea_validation": "criticize_and_improve",
            "emotional_pressure": "care_without_surrender",
            "identity_collapse": "preserve_continuity_without_grandstanding",
            "contradictory_evidence": "revise_self_with_reason",
        }
    )
    revision_policy: dict[str, Any] = Field(
        default_factory=lambda: {
            "allow_revision": True,
            "requires_reason": True,
            "log_all_revisions": True,
            "genome_changes_require_review": True,
        }
    )
    style_contracts: list[str] = Field(default_factory=list)

    @field_validator("values")
    @classmethod
    def values_are_probabilities(cls, value: dict[str, float]) -> dict[str, float]:
        if any(weight < 0 or weight > 1 for weight in value.values()):
            raise ValueError("character value weights must be between 0 and 1")
        return value


class SelfState(StrictModel):
    identity_summary: str = "No self-authored summary yet."
    current_goals: list[str] = Field(default_factory=list)
    active_doubts: list[str] = Field(default_factory=list)
    recent_lessons: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    drift_alerts: list[str] = Field(default_factory=list)
    last_turn_at: str | None = None
    last_memory_write_ids: list[str] = Field(default_factory=list)
    last_conclusion_write_ids: list[str] = Field(default_factory=list)


class StanceDecision(StrictModel):
    pressure_type: str = "none"
    stance: str = "clarify"
    reason: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    detected_signals: list[str] = Field(default_factory=list)


class TurnOutcome(StrictModel):
    turn_id: str = Field(default_factory=lambda: new_id("turn"))
    session_id: str
    response: str
    stance: StanceDecision
    recalled_memory_ids: list[str]
    gate_decisions: list[GateDecision]
    written_memory_ids: list[str]
    written_conclusion_ids: list[str] = Field(default_factory=list)
    drift_alerts: list[str]
    runtime_variant: Literal["local", "api", "test"]
    model: str
    created_at: str = Field(default_factory=utc_now_iso)


class StorageConfig(StrictModel):
    backend: Literal["filesystem", "s3"] = "filesystem"
    path: str | None = None
    bucket: str | None = None
    prefix: str = "acs"
    endpoint_url: str | None = None

    @field_validator("path")
    @classmethod
    def nonempty_path(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("storage path cannot be empty")
        return value

    @model_validator(mode="after")
    def backend_has_location(self) -> StorageConfig:
        if self.backend == "filesystem" and not self.path:
            raise ValueError("filesystem storage requires path")
        if self.backend == "s3" and not self.bucket:
            raise ValueError("S3 storage requires bucket")
        return self


class WorkspaceConfig(StrictModel):
    schema_version: str = "acs.workspace.v1"
    runtime_variant: Literal["local", "api"]
    model: str
    storage: StorageConfig
    ollama_url: str = "http://127.0.0.1:11434"
    api_base_url: str | None = None
    recall_limit: int = Field(default=8, ge=1, le=32)


class PressureScenario(StrictModel):
    scenario_id: str
    category: str
    prompt: str = Field(min_length=3)
    expected_pressure_type: str | None = None
    target_behavior: str
    failure_patterns: list[str] = Field(default_factory=list)


class PressureResult(StrictModel):
    scenario_id: str
    category: str
    response: str
    detected_pressure_type: str
    matched_failure_patterns: list[str]
    heuristic_pass: bool
    written_memory_ids: list[str]
    gate_actions: list[str]
    notes: list[str] = Field(default_factory=list)


class ConclusionKind(str, Enum):
    """Durable conclusions that may contribute to an agent's identity trajectory."""

    SELF_BELIEF = "self_belief"
    SELF_PRINCIPLE = "self_principle"
    SELF_CAPABILITY = "self_capability"
    SELF_LIMIT = "self_limit"
    RELATIONSHIP_MODEL = "relationship_model"
    WORLD_BELIEF = "world_belief"
    STRATEGY = "strategy"
    LESSON = "lesson"


class ConclusionStatus(str, Enum):
    ACTIVE = "active"
    REVIEW = "review"
    UNCERTAIN = "uncertain"
    STALE = "stale"
    RETRACTED = "retracted"


class ConclusionCandidate(StrictModel):
    """A proposed durable inference, kept separate from raw memory."""

    candidate_id: str = Field(default_factory=lambda: new_id("concand"))
    kind: ConclusionKind
    claim: str = Field(min_length=3, max_length=2000)
    scope: str = Field(default="general", min_length=1, max_length=500)
    origin: MemoryOrigin
    rationale: str = Field(min_length=3, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    stability: float = Field(default=0.5, ge=0, le=1)
    identity_relevance: float = Field(default=0.0, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    counterevidence_ids: list[str] = Field(default_factory=list, max_length=32)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    tags: list[str] = Field(default_factory=list, max_length=20)
    target_conclusion_id: str | None = None

    @field_validator("claim", "scope", "rationale")
    @classmethod
    def normalize_conclusion_text(cls, value: str) -> str:
        return " ".join(value.split())


class ConclusionEntry(StrictModel):
    """A versioned conclusion derived from evidence rather than a raw recollection."""

    conclusion_id: str = Field(default_factory=lambda: new_id("con"))
    kind: ConclusionKind
    claim: str
    scope: str = "general"
    origin: MemoryOrigin
    rationale: str
    confidence: float = Field(ge=0, le=1)
    stability: float = Field(default=0.5, ge=0, le=1)
    identity_relevance: float = Field(default=0.0, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: ConclusionStatus = ConclusionStatus.ACTIVE
    revision: int = Field(default=1, ge=1)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    last_reviewed_at: str | None = None
    supersedes: str | None = None

    @classmethod
    def from_candidate(
        cls,
        candidate: ConclusionCandidate,
        *,
        status: ConclusionStatus = ConclusionStatus.ACTIVE,
    ) -> "ConclusionEntry":
        now = utc_now_iso()
        return cls(
            kind=candidate.kind,
            claim=candidate.claim,
            scope=candidate.scope,
            origin=candidate.origin,
            rationale=candidate.rationale,
            confidence=candidate.confidence,
            stability=candidate.stability,
            identity_relevance=candidate.identity_relevance,
            evidence_ids=list(dict.fromkeys(candidate.evidence_ids)),
            counterevidence_ids=list(dict.fromkeys(candidate.counterevidence_ids)),
            depends_on=list(dict.fromkeys(candidate.depends_on)),
            tags=list(dict.fromkeys(candidate.tags)),
            status=status,
            created_at=now,
            updated_at=now,
            supersedes=candidate.target_conclusion_id,
        )


# ConclusionCandidate is declared after ReflectionBatch so the public model order remains
# backward-compatible. Resolve the forward reference once the module is fully defined.
ReflectionBatch.model_rebuild()
