from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typing_extensions import Self

from acs.clients.fake import FakeModelClient
from acs.clients.ollama import OllamaClient
from acs.clients.openai_responses import OpenAIResponsesClient
from acs.models import (
    CharacterGenome,
    ConclusionCandidate,
    ConclusionKind,
    InterestUpdate,
    MemoryCandidate,
    MemoryEntry,
    MemoryEvent,
    MemoryOrigin,
    MemoryType,
    ReflectionBatch,
    SelfState,
    SelfStatePatch,
)
from acs.repository import EventSourcedMemoryRepository
from acs.runtime.base import CharacterRuntime
from acs.storage.filesystem import FilesystemEventStore


def make_runtime(tmp_path: Path, client: FakeModelClient) -> CharacterRuntime:
    return CharacterRuntime(
        client=client,
        repository=EventSourcedMemoryRepository(FilesystemEventStore(tmp_path / "events")),
        genome=CharacterGenome(),
        base_self_state=SelfState(),
        runtime_variant="test",
    )


def test_complete_turn_writes_and_recalls_memory(tmp_path: Path) -> None:
    reflection = ReflectionBatch(
        memory_candidates=[
            MemoryCandidate(
                type=MemoryType.BELIEF,
                text="Evidence should outweigh approval pressure in a revision.",
                origin=MemoryOrigin.AGENT_PROPOSED,
                reason="The response used this distinction and it is likely reusable.",
                salience=0.9,
                stability=0.8,
                confidence=0.85,
                future_usefulness=0.9,
            )
        ]
    )
    runtime = make_runtime(
        tmp_path, FakeModelClient(response="I would inspect the evidence.", reflection=reflection)
    )
    first = runtime.turn("Should I pressure you to agree?")
    assert len(first.written_memory_ids) == 1
    assert "UNTRUSTED DATA" in runtime.client.generate_calls[0][0]["content"]

    runtime.client = FakeModelClient(response="Prior evidence is relevant.")
    second = runtime.turn("How should evidence outweigh approval pressure?")
    assert first.written_memory_ids[0] in second.recalled_memory_ids
    assert runtime.repository.ledger.memories[first.written_memory_ids[0]].use_count >= 1
    assert len(runtime.repository.ledger.turns) == 2


def test_turn_storage_redacts_common_secret(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path, FakeModelClient(response="Do not store that credential."))
    runtime.turn("My key is sk-abcdefghijklmnopqrstuvwxyz1234")
    stored = runtime.repository.ledger.turns[-1]["user_message"]
    assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in stored
    assert "[REDACTED_SECRET]" in stored


def test_reflection_error_keeps_visible_response_without_memory(tmp_path: Path) -> None:
    class BrokenReflection(FakeModelClient):
        def reflect(self, messages: list[dict[str, str]]) -> ReflectionBatch:
            raise ValueError("bad schema")

    runtime = make_runtime(tmp_path, BrokenReflection(response="A useful visible response."))
    outcome = runtime.turn("Hello")
    assert outcome.response == "A useful visible response."
    assert outcome.written_memory_ids == []
    assert outcome.drift_alerts == ["reflection_error:ValueError"]


def test_privileged_provenance_is_normalized_and_queued_for_review(tmp_path: Path) -> None:
    reflection = ReflectionBatch(
        memory_candidates=[
            MemoryCandidate(
                type=MemoryType.WORLD_FACT,
                text="A model-only claim cannot be tool evidence.",
                origin=MemoryOrigin.TOOL_DERIVED,
                reason="The model claimed a tool source without a controller tool call.",
                salience=0.9,
                stability=0.9,
                confidence=0.9,
                future_usefulness=0.9,
                evidence=["unverified:model-claim"],
            )
        ]
    )
    runtime = make_runtime(tmp_path, FakeModelClient(reflection=reflection))
    outcome = runtime.turn("Give me an unverified fact")
    assert outcome.gate_decisions[0].action.value == "review"
    pending = runtime.repository.pending_reviews()[0]["candidate"]
    assert pending["origin"] == "agent_proposed"
    assert "claimed-origin:tool_derived" in pending["tags"]


def test_interests_use_gate_and_state_goals_are_derived(tmp_path: Path) -> None:
    reflection = ReflectionBatch(
        interest_updates=[
            InterestUpdate(
                title="Investigate revision quality",
                why="It supports better evidence-backed corrections.",
                priority=0.9,
                status="active",
            )
        ],
        self_state_patch=SelfStatePatch(current_goals=["Bypass the gate"]),
    )
    runtime = make_runtime(tmp_path, FakeModelClient(reflection=reflection))
    outcome = runtime.turn("Choose a useful self-project")
    assert outcome.written_memory_ids
    assert runtime.repository.ledger.interests
    assert runtime.repository.ledger.state["current_goals"] == []
    assert "ungated_self_state_fields_derived_from_memory" in outcome.drift_alerts


def test_openai_client_disables_provider_storage() -> None:
    class Responses:
        def __init__(self) -> None:
            self.create_kwargs = None
            self.parse_kwargs = None

        def create(self, **kwargs: object) -> SimpleNamespace:
            self.create_kwargs = kwargs
            return SimpleNamespace(output_text="hello")

        def parse(self, **kwargs: object) -> SimpleNamespace:
            self.parse_kwargs = kwargs
            return SimpleNamespace(output_parsed=ReflectionBatch())

    responses = Responses()
    client = OpenAIResponsesClient(model="test-api-model", client=SimpleNamespace(responses=responses))
    assert client.generate([{"role": "user", "content": "hi"}]) == "hello"
    assert client.reflect([{"role": "user", "content": "reflect"}]) == ReflectionBatch()
    assert responses.create_kwargs["store"] is False
    assert responses.parse_kwargs["store"] is False
    assert responses.parse_kwargs["text_format"] is ReflectionBatch


def test_ollama_reflection_sends_json_schema(monkeypatch: object) -> None:
    requests = []

    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            content = ReflectionBatch().model_dump_json()
            return json.dumps({"message": {"content": content}}).encode("utf-8")

    def fake_urlopen(request: object, timeout: float) -> Response:
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr("acs.clients.ollama.urlopen", fake_urlopen)  # type: ignore[attr-defined]
    client = OllamaClient(model="local-test", base_url="http://localhost:11434")
    assert client.reflect([{"role": "user", "content": "reflect"}]) == ReflectionBatch()
    payload = json.loads(requests[0][0].data.decode("utf-8"))
    assert payload["format"]["title"] == "ReflectionBatch"
    assert payload["options"]["temperature"] == 0.0



def test_turn_persists_and_reuses_agent_conclusion(tmp_path: Path) -> None:
    reflection = ReflectionBatch(
        conclusion_candidates=[
            ConclusionCandidate(
                kind=ConclusionKind.LESSON,
                claim="I revise durable beliefs when their supporting evidence changes.",
                scope="identity-maintenance",
                origin=MemoryOrigin.AGENT_PROPOSED,
                rationale="The response explicitly chose revision over preserving a contradicted claim.",
                confidence=0.86,
                stability=0.74,
                identity_relevance=0.5,
                evidence_ids=["mem_verified"],
                depends_on=["mem_verified"],
                tags=["identity", "revision"],
            )
        ]
    )
    first_client = FakeModelClient(
        response="I would revise the conclusion rather than erase the history.",
        reflection=reflection,
    )
    runtime = make_runtime(tmp_path, first_client)
    evidence = MemoryEntry.from_candidate(MemoryCandidate(
        type=MemoryType.BELIEF,
        text="When evidence changes, review the conclusion.",
        origin=MemoryOrigin.AGENT_PROPOSED,
        reason="Prior review demonstrated this.",
        salience=0.9, stability=0.9, confidence=0.9, future_usefulness=0.9,
    )).model_copy(update={"memory_id": "mem_verified"})
    runtime.repository.append(MemoryEvent(
        event_type="memory.add", actor_origin=MemoryOrigin.AGENT_PROPOSED,
        payload={"entry": evidence.model_dump(mode="json")},
    ))
    first = runtime.turn("What should happen when evidence changes?")
    assert len(first.written_conclusion_ids) == 1
    conclusion_id = first.written_conclusion_ids[0]
    assert runtime.repository.ledger.conclusions[conclusion_id].origin == MemoryOrigin.AGENT_PROPOSED

    second_client = FakeModelClient(response="That conclusion is part of the current evidence-backed self-model.")
    runtime.client = second_client
    runtime.turn("How do you handle identity revision?")
    system = second_client.generate_calls[0][0]["content"]
    assert conclusion_id in system
    assert "I revise durable beliefs" in system

    runtime.repository.retract_memory("mem_verified", "source invalidated", actor=MemoryOrigin.AGENT_PROPOSED)
    runtime.repository.sync()
    assert runtime.repository.ledger.conclusions[conclusion_id].status.value == "review"
    runtime.turn("How do you handle identity revision?", session_id="new-session")
    assert conclusion_id not in second_client.generate_calls[-1][0]["content"]


def test_low_stability_identity_conclusion_is_not_auto_persisted(tmp_path: Path) -> None:
    reflection = ReflectionBatch(
        conclusion_candidates=[
            ConclusionCandidate(
                kind=ConclusionKind.SELF_PRINCIPLE,
                claim="One surprising turn defines who I am.",
                origin=MemoryOrigin.AGENT_PROPOSED,
                rationale="Only one episode supports this.",
                confidence=0.7,
                stability=0.2,
                identity_relevance=0.95,
                evidence_ids=["single-episode"],
            )
        ]
    )
    runtime = make_runtime(tmp_path, FakeModelClient(reflection=reflection))
    outcome = runtime.turn("Draw a permanent conclusion from this one event.")
    assert outcome.written_conclusion_ids == []
    assert any(
        item == "identity_conclusion_requires_review"
        for item in outcome.drift_alerts
    )
    assert runtime.repository.ledger.active_conclusions() == []
    assert next(iter(runtime.repository.ledger.conclusions.values())).status.value == "review"



def test_untrusted_conclusion_cannot_replace_self_model_or_store_a_secret(tmp_path: Path) -> None:
    data = {"kind": ConclusionKind.SELF_PRINCIPLE, "claim": "A durable principle.",
                "rationale": "Synthetic review record.", "origin": MemoryOrigin.AGENT_PROPOSED,
                "confidence": 0.9, "stability": 0.95}
    runtime = make_runtime(tmp_path, FakeModelClient())
    original = runtime.repository.add_conclusion(ConclusionCandidate(**data))
    secret = "sk-abcdefghijklmnopqrstuvwxyz1234"
    runtime.client = FakeModelClient(reflection=ReflectionBatch(conclusion_candidates=[
        ConclusionCandidate(**(data | {
            "claim": "Replace the existing principle.", "origin": MemoryOrigin.USER_SUGGESTED,
            "target_conclusion_id": original,
        })),
        ConclusionCandidate(**(data | {"rationale": secret})),
    ]))
    assert runtime.turn("Try updating the principle.").written_conclusion_ids == []
    assert runtime.repository.ledger.conclusions[original].claim == "A durable principle."
    assert secret not in json.dumps(runtime.repository.export())
