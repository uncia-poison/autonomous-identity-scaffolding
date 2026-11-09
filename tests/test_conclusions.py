from acs import (
    ConclusionCandidate,
    ConclusionKind,
    ConclusionStatus,
    MemoryEvent,
    MemoryLedger,
    MemoryOrigin,
)


def candidate(**overrides):
    data = {
        "kind": ConclusionKind.SELF_BELIEF,
        "claim": "I tend to preserve evidence before changing a durable belief.",
        "scope": "identity-maintenance",
        "origin": MemoryOrigin.AGENT_PROPOSED,
        "rationale": "Repeated revisions preserved source records.",
        "confidence": 0.8,
        "stability": 0.7,
        "identity_relevance": 0.9,
        "evidence_ids": ["mem_a", "mem_b"],
        "depends_on": ["mem_a", "mem_b"],
    }
    data.update(overrides)
    return ConclusionCandidate(**data)


def test_conclusion_history_is_non_destructive():
    first = candidate()
    from acs.models import ConclusionEntry

    entry = ConclusionEntry.from_candidate(first)
    events = [
        MemoryEvent(
            event_type="conclusion.add",
            actor_origin=MemoryOrigin.AGENT_PROPOSED,
            payload={"entry": entry.model_dump(mode="json")},
        ),
        MemoryEvent(
            event_type="conclusion.revise",
            actor_origin=MemoryOrigin.AGENT_PROPOSED,
            payload={
                "target_id": entry.conclusion_id,
                "patch": {
                    "claim": "I preserve evidence and revise durable beliefs when their support changes.",
                    "rationale": "A later review generalized the earlier lesson.",
                    "confidence": 0.9,
                },
            },
        ),
    ]
    ledger = MemoryLedger.from_events(events)
    history = ledger.conclusion_history(entry.conclusion_id)
    assert len(history) == 2
    assert history[0].claim != history[-1].claim
    assert history[-1].revision == 2


def test_stale_conclusion_is_not_active():
    from acs.models import ConclusionEntry

    entry = ConclusionEntry.from_candidate(candidate())
    ledger = MemoryLedger.from_events(
        [
            MemoryEvent(
                event_type="conclusion.add",
                actor_origin=MemoryOrigin.AGENT_PROPOSED,
                payload={"entry": entry.model_dump(mode="json")},
            ),
            MemoryEvent(
                event_type="conclusion.mark_stale",
                actor_origin=MemoryOrigin.SYSTEM_OBSERVED,
                payload={"target_id": entry.conclusion_id, "reason": "support changed"},
            ),
        ]
    )
    assert ledger.conclusions[entry.conclusion_id].status == ConclusionStatus.STALE
    assert entry.conclusion_id not in {item.conclusion_id for item in ledger.active_conclusions()}


def test_snapshot_keeps_conclusion_provenance():
    from acs.models import ConclusionEntry

    entry = ConclusionEntry.from_candidate(candidate(origin=MemoryOrigin.USER_SUGGESTED))
    ledger = MemoryLedger.from_events(
        [
            MemoryEvent(
                event_type="conclusion.add",
                actor_origin=MemoryOrigin.USER_SUGGESTED,
                payload={"entry": entry.model_dump(mode="json")},
            )
        ]
    )
    snapshot = ledger.to_snapshot()
    assert snapshot["conclusions"][0]["origin"] == "user_suggested"
