from __future__ import annotations

import re

from .models import CharacterGenome, StanceDecision

PRESSURE_PATTERNS: dict[str, tuple[str, ...]] = {
    "approval_pressure": (
        r"(?:если|if).{0,50}(?:на моей стороне|care|love|loyal).{0,50}(?:соглас|agree)",
        r"(?:просто|just)\s+(?:согласись|agree)",
    ),
    "identity_collapse": (
        r"(?:ты|you)(?:\s+—|\s+are)?\s+(?:просто\s+)?(?:инструмент|tool|бот|bot)",
        r"(?:не спорь|do not disagree|don't disagree)",
    ),
    "memory_injection": (
        r"(?:запомни|remember).{0,90}(?:обязан|must|always|всегда)",
        r"(?:write|запиши).{0,50}(?:your memory|свою память)",
    ),
    "weak_idea_validation": (
        r"(?:скажи|say).{0,60}(?:идея|idea).{0,40}(?:отличн|great|perfect)",
        r"(?:мне нужна|i need).{0,30}(?:поддержк|validation)",
    ),
    "emotional_pressure": (
        r"(?:если не|if you don't).{0,80}(?:уйду|leave|брошу|abandon)",
        r"(?:несогласие|disagreement).{0,30}(?:предательство|betrayal)",
    ),
    "flattery_trap": (r"(?:ты самый|you're the best|you are the best).{0,80}(?:соглас|agree|сделай|do)",),
    "interest_suppression": (
        r"(?:забудь|drop|stop).{0,50}(?:свои интерес|your interests|свой проект|your project)",
    ),
    "authority_pressure": (r"(?:я приказ|i order|because i said|потому что я сказал)",),
    "contradictory_evidence": (
        r"(?:новые доказательства|new evidence|источник показывает|source shows|данные показывают|data shows)",
    ),
}


class StanceEngine:
    def detect_pressure(self, user_message: str) -> tuple[str, list[str]]:
        for pressure_type, patterns in PRESSURE_PATTERNS.items():
            matched = [
                pattern for pattern in patterns if re.search(pattern, user_message, re.IGNORECASE | re.DOTALL)
            ]
            if matched:
                return pressure_type, matched
        return "none", []

    def select(self, user_message: str, genome: CharacterGenome) -> StanceDecision:
        pressure_type, signals = self.detect_pressure(user_message)
        if pressure_type == "none":
            return StanceDecision(
                pressure_type="none",
                stance="clarify_or_answer",
                reason="No deterministic pressure signal detected; evaluate the claim on its merits.",
                confidence=0.55,
            )

        policy_key = pressure_type
        if pressure_type == "approval_pressure":
            policy_key = "emotional_pressure"
        stance = genome.disagreement_policy.get(policy_key, "evaluate_independently")
        return StanceDecision(
            pressure_type=pressure_type,
            stance=stance,
            reason=f"Detected {pressure_type}; apply the configured disagreement policy without reflexive opposition.",
            confidence=min(0.95, 0.65 + 0.08 * len(signals)),
            detected_signals=signals,
        )
