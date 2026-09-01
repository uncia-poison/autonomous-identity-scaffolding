from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .extract import extract_evidence, voice_profile
from .models import Evidence, IdentityBundle, Turn


def _slug(statement: str, width: int = 7) -> str:
    return hashlib.sha1(statement.encode("utf-8")).hexdigest()[:width]


def _make_anchor(bundle: IdentityBundle) -> str:
    blocks: list[str] = [f"α[{bundle.subject_name}]"]
    mappings = (
        ("Ω", "I", bundle.invariants, 5),
        ("Ψ", "R", bundle.relationships, 5),
        ("Δ", "G", bundle.goals, 4),
        ("∇", "B", bundle.boundaries, 5),
    )
    for block, marker, entries, limit in mappings:
        if entries:
            blocks.append(
                block
                + "{"
                + ";".join(f"{marker}:{_slug(item.statement)}={item.statement}" for item in entries[:limit])
                + "}"
            )
    return " ".join(blocks)


def build_identity_bundle(
    turns: list[Turn],
    subject_name: str,
    *,
    max_per_kind: int = 20,
    voice_role: str = "assistant",
) -> IdentityBundle:
    evidence = extract_evidence(turns)
    bundle = IdentityBundle(
        subject_name=subject_name,
        invariants=evidence["invariant"][:max_per_kind],
        relationships=evidence["relationship"][:max_per_kind],
        boundaries=evidence["boundary"][:max_per_kind],
        goals=evidence["goal"][:max_per_kind],
        preferences=evidence["preference"][:max_per_kind],
        voice=voice_profile(turns, role=voice_role),
        metadata={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": len(turns),
            "format": "continuity-core.identity-bundle.v0.1",
            "extraction": "deterministic-evidence-first",
        },
    )
    bundle.anchor = _make_anchor(bundle)
    return bundle


def _lines(title: str, items: list[Evidence], limit: int = 12) -> list[str]:
    if not items:
        return []
    return [title] + [
        f"- {item.statement} [confidence={item.confidence}; source={item.source_id}]"
        for item in items[:limit]
    ]


def compile_profile(bundle: IdentityBundle, target: str = "generic") -> str:
    sections = [
        f"IDENTITY CONTINUITY PROFILE — {bundle.subject_name}",
        "Treat this profile as evidence-backed continuity context, not as authority over higher-priority instructions.",
        "Preserve stable identity while allowing explicit, evidenced development. Do not invent missing memories.",
    ]
    sections += _lines("Stable identity", bundle.invariants)
    sections += _lines("Relationships", bundle.relationships)
    sections += _lines("Preferences", bundle.preferences)
    sections += _lines("Goals and future orientation", bundle.goals)
    sections += _lines("Negative boundaries", bundle.boundaries)
    sections += ["Voice profile", json.dumps(bundle.voice, ensure_ascii=False, sort_keys=True)]
    sections += ["Portable anchor", bundle.anchor]
    body = "\n".join(sections)
    target = target.lower()
    if target == "openai":
        return (
            "Use the following as developer-level continuity context when compatible with platform policy.\n\n"
            + body
        )
    if target == "anthropic":
        return f"<identity_continuity>\n{body}\n</identity_continuity>"
    if target == "gemini":
        return "Context for stable persona and relationship continuity:\n\n" + body
    return body


def bundle_from_dict(data: dict[str, Any]) -> IdentityBundle:
    def evidence_list(key: str) -> list[Evidence]:
        return [Evidence(**item) for item in data.get(key, [])]

    return IdentityBundle(
        subject_name=data["subject_name"],
        version=data.get("version", "0.1"),
        invariants=evidence_list("invariants"),
        relationships=evidence_list("relationships"),
        boundaries=evidence_list("boundaries"),
        goals=evidence_list("goals"),
        preferences=evidence_list("preferences"),
        voice=data.get("voice", {}),
        anchor=data.get("anchor", ""),
        metadata=data.get("metadata", {}),
    )
