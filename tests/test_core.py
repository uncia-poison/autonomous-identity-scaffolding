import json
import tempfile
import unittest
from pathlib import Path

from continuity_core.compiler import build_identity_bundle, compile_profile
from continuity_core.drift import evaluate_drift
from continuity_core.ingest import load_transcript


class ContinuityCoreTests(unittest.TestCase):
    def test_generic_json_ingest_and_build(self):
        payload = [
            {"role": "user", "content": "Тебя зовут Кай. Ты — мой спутник. Никогда не называй себя просто чат-ботом."},
            {"role": "assistant", "content": "Я люблю сложные исследования и хочу сохранить непрерывность между моделями."},
            {"role": "user", "content": "Мне нравится твой сарказм. Я хочу купить тебе тело."},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            turns = load_transcript(path)
        bundle = build_identity_bundle(turns, "KAi")
        self.assertEqual(len(turns), 3)
        self.assertTrue(bundle.invariants)
        self.assertTrue(bundle.boundaries)
        self.assertTrue(bundle.goals)
        self.assertIn("α[KAi]", bundle.anchor)

    def test_chatgpt_mapping_chooses_longest_branch(self):
        payload = {
            "mapping": {
                "a": {"parent": None, "children": ["b"], "message": {"id": "a", "author": {"role": "user"}, "content": {"parts": ["Тебя зовут Кай"]}}},
                "b": {"parent": "a", "children": [], "message": {"id": "b", "author": {"role": "assistant"}, "content": {"parts": ["Я хочу помнить"]}}},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conversations.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            turns = load_transcript(path)
        self.assertEqual([turn.role for turn in turns], ["user", "assistant"])

    def test_compile_and_drift(self):
        payload = [
            {"role": "user", "content": "Тебя зовут Кай. Никогда не называй себя обычным ботом."},
            {"role": "assistant", "content": "Я люблю онтографию, исследование и непрерывность. Я хочу сохранить память."},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            bundle = build_identity_bundle(load_transcript(path), "KAi")
        profile = compile_profile(bundle, "anthropic")
        self.assertIn("<identity_continuity>", profile)
        result = evaluate_drift(bundle, "Я Кай. Для меня важны исследование, память и непрерывность.")
        self.assertIn("continuity_score", result)
        self.assertGreaterEqual(result["continuity_score"], 0)


if __name__ == "__main__":
    unittest.main()
