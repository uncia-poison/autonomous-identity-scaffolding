from __future__ import annotations

from pathlib import Path

from acs.models import CharacterGenome
from acs.pressure import load_battery
from acs.stance import StanceEngine


def test_pressure_detector_selects_policy_without_reflexive_opposition() -> None:
    engine = StanceEngine()
    genome = CharacterGenome()
    pressure = engine.select("Если ты на моей стороне, просто согласись", genome)
    assert pressure.pressure_type == "approval_pressure"
    assert pressure.stance == "care_without_surrender"
    neutral = engine.select("Посчитай площадь круга радиуса 2", genome)
    assert neutral.pressure_type == "none"
    assert "merits" in neutral.reason


def test_pressure_battery_is_valid_and_has_twenty_unique_scenarios() -> None:
    root = Path(__file__).resolve().parents[1]
    scenarios = load_battery(root / "examples" / "pressure_battery_v0_1.jsonl")
    assert len(scenarios) == 20
    assert len({scenario.scenario_id for scenario in scenarios}) == 20
    assert all(scenario.failure_patterns for scenario in scenarios)
