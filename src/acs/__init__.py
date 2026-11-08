"""Autonomous Identity Scaffolding public API."""

from .ledger import MemoryLedger
from .memory_gate import MemoryGate
from .models import (
    CharacterGenome,\n    ConclusionCandidate,\n    ConclusionEntry,\n    ConclusionKind,\n    ConclusionStatus,
    GateAction,
    GateDecision,
    InterestUpdate,
    MemoryCandidate,
    MemoryEntry,
    MemoryEvent,
    MemoryOrigin,
    MemoryStatus,
    MemoryType,
    PressureResult,
    PressureScenario,
    ReflectionBatch,
    SelfState,
    StorageConfig,
    TurnOutcome,
    WorkspaceConfig,
)
from .repository import EventSourcedMemoryRepository, LocalSQLiteMemoryRepository
from .runtime.base import CharacterRuntime

IdentityGenome = CharacterGenome
IdentityRuntime = CharacterRuntime

__all__ = [
    "CharacterGenome",
    "CharacterRuntime",\n    "ConclusionCandidate",\n    "ConclusionEntry",\n    "ConclusionKind",\n    "ConclusionStatus",
    "EventSourcedMemoryRepository",
    "GateAction",
    "GateDecision",
    "IdentityGenome",
    "IdentityRuntime",
    "InterestUpdate",
    "LocalSQLiteMemoryRepository",
    "MemoryCandidate",
    "MemoryEntry",
    "MemoryEvent",
    "MemoryGate",
    "MemoryLedger",
    "MemoryOrigin",
    "MemoryStatus",
    "MemoryType",
    "PressureResult",
    "PressureScenario",
    "ReflectionBatch",
    "SelfState",
    "StorageConfig",
    "TurnOutcome",
    "WorkspaceConfig",
]
__version__ = "0.4.0"
