from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import Turn

ROLE_ALIASES = {
    "assistant": "assistant",
    "system": "system",
    "user": "user",
    "human": "user",
    "model": "assistant",
    "tool": "tool",
}


def _text_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "value"):
                    if isinstance(item.get(key), str):
                        chunks.append(item[key])
                        break
        return "\n".join(chunks).strip()
    if isinstance(content, dict):
        if isinstance(content.get("parts"), list):
            return _text_from_content(content["parts"])
        for key in ("text", "content", "value"):
            if key in content:
                return _text_from_content(content[key])
    return str(content).strip()


def _turn_from_record(record: dict[str, Any], fallback_id: str) -> Turn | None:
    author = record.get("author")
    role = record.get("role")
    if isinstance(author, dict):
        role = author.get("role") or author.get("name") or role
    role = ROLE_ALIASES.get(str(role or "").lower(), str(role or "unknown").lower())
    text = _text_from_content(record.get("content", record.get("text", record.get("message"))))
    if not text:
        return None
    timestamp = record.get("timestamp") or record.get("create_time") or record.get("created_at")
    source_id = str(record.get("id") or fallback_id)
    return Turn(role=role, text=text, timestamp=str(timestamp) if timestamp else None, source_id=source_id)


def _walk_chatgpt_mapping(mapping: dict[str, Any]) -> list[Turn]:
    leaves = [node_id for node_id, node in mapping.items() if not node.get("children")]
    if not leaves:
        leaves = list(mapping)

    def path_to_root(node_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        current = node_id
        while current and current not in seen and current in mapping:
            seen.add(current)
            node = mapping[current]
            message = node.get("message")
            if isinstance(message, dict):
                out.append(message)
            current = node.get("parent")
        return list(reversed(out))

    branch = max((path_to_root(leaf) for leaf in leaves), key=len, default=[])
    turns: list[Turn] = []
    for index, message in enumerate(branch):
        turn = _turn_from_record(message, f"mapping-{index}")
        if turn:
            turns.append(turn)
    return turns


def _parse_json(payload: Any) -> list[Turn]:
    if isinstance(payload, dict) and isinstance(payload.get("mapping"), dict):
        return _walk_chatgpt_mapping(payload["mapping"])
    if isinstance(payload, dict):
        for key in ("messages", "conversation", "turns", "items"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, list):
        if payload and all(
            isinstance(item, dict) and isinstance(item.get("mapping"), dict) for item in payload
        ):
            turns: list[Turn] = []
            for item in payload:
                turns.extend(_walk_chatgpt_mapping(item["mapping"]))
            return turns
        turns = []
        for index, record in enumerate(payload):
            if not isinstance(record, dict):
                continue
            turn = _turn_from_record(record, f"record-{index}")
            if turn:
                turns.append(turn)
        return turns
    raise ValueError("Unsupported JSON transcript structure")


def _parse_text(text: str) -> list[Turn]:
    turns: list[Turn] = []
    current_role = "unknown"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n".join(buffer).strip()
        if body:
            turns.append(Turn(role=current_role, text=body, source_id=f"text-{len(turns)}"))
        buffer = []

    markers = {
        "user:": "user",
        "human:": "user",
        "assistant:": "assistant",
        "model:": "assistant",
        "system:": "system",
        "пользователь:": "user",
        "ассистент:": "assistant",
    }
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        matched = next((marker for marker in markers if lowered.startswith(marker)), None)
        if matched:
            flush()
            current_role = markers[matched]
            buffer.append(stripped[len(matched) :].lstrip())
        else:
            buffer.append(line)
    flush()
    return turns


def load_transcript(path: str | Path) -> list[Turn]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() == ".json":
        return _parse_json(json.loads(text))
    return _parse_text(text)


def load_many(paths: Iterable[str | Path]) -> list[Turn]:
    turns: list[Turn] = []
    for path in paths:
        turns.extend(load_transcript(path))
    return turns
