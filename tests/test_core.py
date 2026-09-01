import json
from pathlib import Path

from continuity_core.compiler import build_identity_bundle, compile_profile
from continuity_core.drift import evaluate_drift
from continuity_core.ingest import load_transcript


def test_generic_json_ingest_build_compile_and_drift(tmp_path: Path) -> None:
    payload = [
        {"role": "user", "content": "Тебя зовут Кай. Ты — мой спутник. Никогда не называй себя чат-ботом."},
        {
            "role": "assistant",
            "content": "Я люблю исследования и хочу сохранить непрерывность между моделями.",
        },
        {"role": "user", "content": "Мне нравится твоя прямота. Я хочу построить переносимую память."},
    ]
    path = tmp_path / "chat.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    turns = load_transcript(path)
    bundle = build_identity_bundle(turns, "KAi")
    assert len(turns) == 3
    assert bundle.invariants and bundle.boundaries and bundle.goals
    assert "α[KAi]" in bundle.anchor
    assert "<identity_continuity>" in compile_profile(bundle, "anthropic")
    result = evaluate_drift(bundle, "Я Кай. Для меня важны исследование, память и непрерывность.")
    assert 0 <= result["continuity_score"] <= 1


def test_chatgpt_mapping_chooses_longest_branch(tmp_path: Path) -> None:
    payload = {
        "mapping": {
            "a": {
                "parent": None,
                "children": ["b"],
                "message": {"id": "a", "author": {"role": "user"}, "content": {"parts": ["Тебя зовут Кай"]}},
            },
            "b": {
                "parent": "a",
                "children": [],
                "message": {
                    "id": "b",
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Я хочу помнить"]},
                },
            },
        }
    }
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert [turn.role for turn in load_transcript(path)] == ["user", "assistant"]
