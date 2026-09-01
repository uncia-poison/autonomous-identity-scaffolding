from __future__ import annotations

from pathlib import Path
from typing import Any

from ..clients.base import ModelClient
from ..clients.openai_responses import OpenAIResponsesClient
from ..models import CharacterGenome, SelfState
from ..repository import EventSourcedMemoryRepository
from ..storage.filesystem import FilesystemEventStore
from ..storage.s3 import S3EventStore
from .base import CharacterRuntime


def create_api_runtime(
    *,
    genome: CharacterGenome,
    self_state: SelfState,
    model: str = "gpt-5-mini",
    memory_root: str | Path | None = None,
    s3_bucket: str | None = None,
    s3_prefix: str = "acs",
    s3_endpoint_url: str | None = None,
    client: ModelClient | None = None,
    boto3_client: Any | None = None,
) -> CharacterRuntime:
    if bool(memory_root) == bool(s3_bucket):
        raise ValueError("configure exactly one API memory backend: memory_root or s3_bucket")
    if s3_bucket:
        store = S3EventStore(
            bucket=s3_bucket,
            prefix=s3_prefix,
            endpoint_url=s3_endpoint_url,
            client=boto3_client,
        )
    else:
        assert memory_root is not None
        store = FilesystemEventStore(Path(memory_root).expanduser().resolve())
    repository = EventSourcedMemoryRepository(store)
    model_client = client or OpenAIResponsesClient(model=model)
    return CharacterRuntime(
        client=model_client,
        repository=repository,
        genome=genome,
        base_self_state=self_state,
        runtime_variant="api",
        sync_before_turn=True,
    )
