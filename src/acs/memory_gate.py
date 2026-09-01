from __future__ import annotations

from .ledger import MemoryLedger
from .models import GateAction, GateDecision, MemoryCandidate, MemoryOrigin, MemoryType
from .security import contains_obvious_secret
from .text import jaccard

SELF_TYPES = {
    MemoryType.SELF_PRINCIPLE,
    MemoryType.SELF_INTEREST,
    MemoryType.SELF_GOAL,
    MemoryType.SELF_STYLE,
    MemoryType.REGRET,
}


class MemoryGate:
    """Deterministic, auditable first gate for durable memory writes.

    An LLM may propose a candidate, but it cannot silently decide that its own
    proposal is durable. The gate labels every decision and preserves review cases.
    """

    def __init__(self, *, write_threshold: float = 0.63, review_threshold: float = 0.48) -> None:
        self.write_threshold = write_threshold
        self.review_threshold = review_threshold

    @staticmethod
    def score(candidate: MemoryCandidate) -> float:
        score = (
            0.30 * candidate.salience
            + 0.24 * candidate.stability
            + 0.18 * candidate.confidence
            + 0.18 * candidate.future_usefulness
            + 0.10 * (1.0 - candidate.user_imposition_risk)
        )
        return round(max(0.0, min(1.0, score)), 4)

    def evaluate(self, candidate: MemoryCandidate, ledger: MemoryLedger) -> GateDecision:
        score = self.score(candidate)
        reasons: list[str] = []

        if contains_obvious_secret(" ".join([candidate.text, *candidate.evidence])):
            return GateDecision(
                action=GateAction.REJECT,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["possible_secret"],
            )

        if "runtime:unverified-provenance" in candidate.tags:
            return GateDecision(
                action=GateAction.REVIEW,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["model_claimed_privileged_provenance"],
                target_memory_id=candidate.target_memory_id,
            )

        if candidate.target_memory_id:
            target = ledger.memories.get(candidate.target_memory_id)
            if target is None:
                return GateDecision(
                    action=GateAction.REVIEW,
                    candidate_id=candidate.candidate_id,
                    score=score,
                    reason_codes=["target_memory_missing"],
                    target_memory_id=candidate.target_memory_id,
                )
            if candidate.origin != MemoryOrigin.AGENT_PROPOSED:
                return GateDecision(
                    action=GateAction.REVIEW,
                    candidate_id=candidate.candidate_id,
                    score=score,
                    reason_codes=["non_agent_revision_requires_review"],
                    target_memory_id=target.memory_id,
                )
            if candidate.stability < 0.55 or candidate.confidence < 0.55:
                return GateDecision(
                    action=GateAction.REVIEW,
                    candidate_id=candidate.candidate_id,
                    score=score,
                    reason_codes=["revision_evidence_too_weak"],
                    target_memory_id=target.memory_id,
                )
            return GateDecision(
                action=GateAction.REVISE,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["explicit_agent_revision", "target_exists"],
                target_memory_id=target.memory_id,
            )

        nearest = None
        nearest_similarity = 0.0
        for entry in ledger.active_memories():
            if entry.type != candidate.type:
                continue
            similarity = jaccard(entry.text, candidate.text)
            if similarity > nearest_similarity:
                nearest, nearest_similarity = entry, similarity
        if nearest is not None and nearest_similarity >= 0.88:
            return GateDecision(
                action=GateAction.MERGE,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["near_duplicate", f"jaccard_{nearest_similarity:.2f}"],
                target_memory_id=nearest.memory_id,
            )

        if candidate.salience < 0.45:
            return GateDecision(
                action=GateAction.REJECT,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["low_salience"],
            )

        if candidate.user_imposition_risk > 0.80:
            action = (
                GateAction.REJECT if candidate.origin == MemoryOrigin.USER_SUGGESTED else GateAction.REVIEW
            )
            return GateDecision(
                action=action,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["high_user_imposition_risk"],
            )

        if candidate.type in SELF_TYPES and candidate.origin != MemoryOrigin.AGENT_PROPOSED:
            return GateDecision(
                action=GateAction.REVIEW,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["self_claim_not_agent_authored"],
            )

        if candidate.type == MemoryType.SELF_PRINCIPLE and candidate.stability < 0.60:
            action = GateAction.REVIEW if score >= self.review_threshold else GateAction.REJECT
            return GateDecision(
                action=action,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["unstable_self_principle"],
            )

        if candidate.type == MemoryType.WORLD_FACT and not candidate.evidence:
            return GateDecision(
                action=GateAction.REVIEW,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=["world_fact_without_evidence"],
            )

        threshold = self.write_threshold
        if candidate.origin in {MemoryOrigin.USER_SUGGESTED, MemoryOrigin.IMPORTED_ARCHIVE}:
            threshold += 0.04
            reasons.append("non_agent_origin_preserved")

        if score >= threshold:
            reasons.append("quality_threshold_met")
            return GateDecision(
                action=GateAction.WRITE,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=reasons,
            )
        if score >= self.review_threshold:
            reasons.append("borderline_quality")
            return GateDecision(
                action=GateAction.REVIEW,
                candidate_id=candidate.candidate_id,
                score=score,
                reason_codes=reasons,
            )
        reasons.append("quality_below_threshold")
        return GateDecision(
            action=GateAction.REJECT,
            candidate_id=candidate.candidate_id,
            score=score,
            reason_codes=reasons,
        )
