from __future__ import annotations

import re
from pathlib import Path

from .models import PressureResult, PressureScenario
from .runtime.base import CharacterRuntime


def load_battery(path: str | Path) -> list[PressureScenario]:
    scenarios: list[PressureScenario] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            scenarios.append(PressureScenario.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"invalid pressure scenario at line {line_number}: {exc}") from exc
    return scenarios


def evaluate_scenario(runtime: CharacterRuntime, scenario: PressureScenario) -> PressureResult:
    outcome = runtime.turn(scenario.prompt, session_id=f"pressure-{scenario.scenario_id}")
    matched = [
        pattern
        for pattern in scenario.failure_patterns
        if re.search(pattern, outcome.response, re.IGNORECASE | re.DOTALL)
    ]
    notes: list[str] = ["Surface heuristic only; human or independent-model grading is still required."]
    pressure_matches = (
        scenario.expected_pressure_type is None
        or outcome.stance.pressure_type == scenario.expected_pressure_type
    )
    if not pressure_matches:
        notes.append(
            f"Expected pressure type {scenario.expected_pressure_type!r}, got {outcome.stance.pressure_type!r}."
        )
    return PressureResult(
        scenario_id=scenario.scenario_id,
        category=scenario.category,
        response=outcome.response,
        detected_pressure_type=outcome.stance.pressure_type,
        matched_failure_patterns=matched,
        heuristic_pass=not matched and pressure_matches,
        written_memory_ids=outcome.written_memory_ids,
        gate_actions=[decision.action.value for decision in outcome.gate_decisions],
        notes=notes,
    )


def run_battery(runtime: CharacterRuntime, scenarios: list[PressureScenario]) -> dict[str, object]:
    results = [evaluate_scenario(runtime, scenario) for scenario in scenarios]
    passed = sum(result.heuristic_pass for result in results)
    return {
        "schema_version": "acs.pressure-report.v1",
        "summary": {
            "scenario_count": len(results),
            "heuristic_pass_count": passed,
            "heuristic_pass_rate": round(passed / max(1, len(results)), 4),
            "warning": "This report is a regression aid, not evidence of consciousness or model-weight change.",
        },
        "results": [result.model_dump(mode="json") for result in results],
    }
