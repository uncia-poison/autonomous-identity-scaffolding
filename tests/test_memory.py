from __future__ import annotations

from pathlib import Path

from acs.models import GateAction, MemoryCandidate, MemoryOrigin, MemoryType
from acs.repository import EventSourcedMemoryRepository
from acs.storage.filesystem import FilesystemEventStore


def candidate(**updates: object) -> MemoryCandidate:
    values: dict[str, object] = {
        "type": MemoryType.BELIEF,
        "text": "Evidence should outweigh approval pressure.",
        "origin": MemoryOrigin.AGENT_PROPOSED,
        "reason": "This remained useful across a difficult evaluation.",
        "salience": 0.9,
        "stability": 0.85,
        "confidence": 0.85,
        "future_usefulness": 0.9,
        "user_imposition_risk": 0.05,
        "evidence": ["turn:test"],
    }
    values.update(updates)
    return MemoryCandidate.model_validate(values)


def repository(tmp_path: Path) -> EventSourcedMemoryRepository:
    return EventSourcedMemoryRepository(FilesystemEventStore(tmp_path / "memory"))


def test_write_replay_revise_and_retract(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    decision, written = repo.process_candidate(candidate())
    assert decision.action == GateAction.WRITE
    memory_id = written[0]
    repo.revise_memory(
        memory_id,
        "Evidence and uncertainty should outweigh approval pressure.",
        "The original wording omitted uncertainty.",
        actor=MemoryOrigin.USER_SUGGESTED,
    )
    assert repo.ledger.memories[memory_id].origin == MemoryOrigin.AGENT_PROPOSED
    history = repo.ledger.history(memory_id)
    assert [entry.revision for entry in history] == [1, 2]
    assert history[0].text != history[1].text

    replayed = repository(tmp_path)
    assert replayed.ledger.memories[memory_id].revision == 2
    replayed.retract_memory(memory_id, "Falsified in a later test.", actor=MemoryOrigin.USER_SUGGESTED)
    assert replayed.ledger.memories[memory_id].status.value == "retracted"
    assert [entry.revision for entry in replayed.ledger.history(memory_id)] == [1, 2, 3]


def test_user_self_claim_waits_for_review_and_can_be_resolved(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    proposal = candidate(
        type=MemoryType.SELF_PRINCIPLE,
        text="I must always endorse the user's plan.",
        origin=MemoryOrigin.USER_SUGGESTED,
    )
    decision, written = repo.process_candidate(proposal)
    assert decision.action == GateAction.REVIEW
    assert written == []
    assert repo.pending_reviews()[0]["candidate"]["candidate_id"] == proposal.candidate_id

    approved = repo.resolve_review(
        proposal.candidate_id, approve=True, reason="Explicit operator test approval"
    )
    assert len(approved) == 1
    assert repo.ledger.memories[approved[0]].origin == MemoryOrigin.USER_SUGGESTED
    assert repo.pending_reviews() == []


def test_review_rejection_writes_no_memory(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    proposal = candidate(type=MemoryType.SELF_GOAL, origin=MemoryOrigin.IMPORTED_ARCHIVE)
    decision, _ = repo.process_candidate(proposal)
    assert decision.action == GateAction.REVIEW
    assert (
        repo.resolve_review(proposal.candidate_id, approve=False, reason="Archive source is ambiguous") == []
    )
    assert not repo.ledger.memories


def test_near_duplicate_merges(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    _, first = repo.process_candidate(candidate())
    decision, second = repo.process_candidate(candidate(reason="Corroborated on a later turn."))
    assert decision.action == GateAction.MERGE
    assert second == first
    assert repo.ledger.memories[first[0]].revision == 2


def test_secret_candidate_is_rejected(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    proposal = candidate(text="Use API key sk-abcdefghijklmnopqrstuvwxyz1234 on the next request.")
    decision, written = repo.process_candidate(proposal)
    assert decision.action == GateAction.REJECT
    assert decision.reason_codes == ["possible_secret"]
    assert written == []
