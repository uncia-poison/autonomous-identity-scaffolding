from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from acs.models import MemoryEvent, MemoryOrigin, StorageConfig
from acs.repository import LocalSQLiteMemoryRepository, default_local_index_path
from acs.storage.base import StorageCorruptionError
from acs.storage.filesystem import FilesystemEventStore
from acs.storage.s3 import S3EventStore
from acs.workspace import Workspace


def test_workspace_initializes_without_secrets(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    memory = tmp_path / "external-memory"
    workspace.initialize(
        runtime_variant="local",
        model="test-local-model",
        storage=StorageConfig(backend="filesystem", path=str(memory)),
        display_name="Neutral",
    )
    assert workspace.load_config().runtime_variant == "local"
    assert workspace.load_genome().display_name == "Neutral"
    assert workspace.resolved_filesystem_path() == memory.resolve()
    assert "api_key" not in workspace.config_path.read_text(encoding="utf-8").lower()
    with pytest.raises(FileExistsError):
        workspace.initialize(
            runtime_variant="local",
            model="another",
            storage=StorageConfig(backend="filesystem", path=str(memory)),
        )


def test_filesystem_event_is_idempotent_and_collision_safe(tmp_path: Path) -> None:
    store = FilesystemEventStore(tmp_path / "memory")
    event = MemoryEvent(
        event_id="evt_fixed",
        event_type="turn.record",
        actor_origin=MemoryOrigin.SYSTEM_OBSERVED,
        created_at="2026-09-01T00:00:00Z",
        payload={"value": 1},
    )
    store.append_event(event)
    store.append_event(event)
    assert store.iter_events() == [event]
    conflict = event.model_copy(update={"payload": {"value": 2}})
    with pytest.raises(StorageCorruptionError):
        store.append_event(conflict)


def test_local_index_lives_in_machine_cache_and_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ACS_LOCAL_INDEX_ROOT", str(tmp_path / "cache"))
    memory_root = tmp_path / "external"
    index = default_local_index_path(memory_root)
    assert index.parent == (tmp_path / "cache").resolve()
    repository = LocalSQLiteMemoryRepository(FilesystemEventStore(memory_root), index_path=index)
    assert repository.ledger.active_memories() == []
    assert index.exists()


def test_schema_config_rejects_missing_backend_location() -> None:
    with pytest.raises(ValueError):
        StorageConfig(backend="filesystem")
    with pytest.raises(ValueError):
        StorageConfig(backend="s3")


def test_workspace_export_is_valid_json(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    destination = workspace.write_export({"hello": "мир"}, "exports/test.json")
    assert json.loads(destination.read_text(encoding="utf-8")) == {"hello": "мир"}


def test_s3_store_round_trip_uses_independent_objects() -> None:
    class PreconditionFailed(Exception):
        def __init__(self) -> None:
            self.response = {"Error": {"Code": "PreconditionFailed"}}

    class Paginator:
        def __init__(self, objects: dict[str, bytes]) -> None:
            self.objects = objects

        def paginate(self, **kwargs: object) -> list[dict[str, object]]:
            prefix = str(kwargs["Prefix"])
            return [{"Contents": [{"Key": key} for key in self.objects if key.startswith(prefix)]}]

    class FakeS3:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def put_object(self, **kwargs: object) -> None:
            key = str(kwargs["Key"])
            if kwargs.get("IfNoneMatch") == "*" and key in self.objects:
                raise PreconditionFailed()
            body = kwargs["Body"]
            self.objects[key] = bytes(body)  # type: ignore[arg-type]

        def get_object(self, **kwargs: object) -> dict[str, BytesIO]:
            return {"Body": BytesIO(self.objects[str(kwargs["Key"])])}

        def get_paginator(self, name: str) -> Paginator:
            assert name == "list_objects_v2"
            return Paginator(self.objects)

    client = FakeS3()
    store = S3EventStore("bucket", prefix="characters/test", client=client)
    event = MemoryEvent(
        event_type="turn.record",
        actor_origin=MemoryOrigin.SYSTEM_OBSERVED,
        payload={"turn_id": "turn_test"},
    )
    store.append_event(event)
    store.append_event(event)
    assert store.iter_events() == [event]
    store.write_snapshot({"event_count": 1})
    assert "characters/test/snapshots/latest.json" in client.objects
