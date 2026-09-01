from __future__ import annotations

from pathlib import Path

from ..clients.base import ModelClient
from ..clients.ollama import OllamaClient
from ..models import CharacterGenome, SelfState
from ..repository import LocalSQLiteMemoryRepository, default_local_index_path
from ..storage.filesystem import FilesystemEventStore
from .base import CharacterRuntime


def create_local_runtime(
    *,
    memory_root: str | Path,
    genome: CharacterGenome,
    self_state: SelfState,
    model: str = "qwen3:8b",
    ollama_url: str = "http://127.0.0.1:11434",
    client: ModelClient | None = None,
) -> CharacterRuntime:
    root = Path(memory_root).expanduser().resolve()
    store = FilesystemEventStore(root)
    repository = LocalSQLiteMemoryRepository(store, index_path=default_local_index_path(root))
    model_client = client or OllamaClient(model=model, base_url=ollama_url)
    return CharacterRuntime(
        client=model_client,
        repository=repository,
        genome=genome,
        base_self_state=self_state,
        runtime_variant="local",
    )
