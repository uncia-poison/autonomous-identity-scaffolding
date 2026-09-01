from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import CharacterGenome, SelfState, StorageConfig, WorkspaceConfig


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Workspace:
    """Human-editable character config plus a pointer to canonical external memory."""

    CONFIG_NAME = "acs.json"
    GENOME_NAME = "character_genome.json"
    SELF_STATE_NAME = "self_state.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    @property
    def config_path(self) -> Path:
        return self.root / self.CONFIG_NAME

    @property
    def genome_path(self) -> Path:
        return self.root / self.GENOME_NAME

    @property
    def self_state_path(self) -> Path:
        return self.root / self.SELF_STATE_NAME

    def initialize(
        self,
        *,
        runtime_variant: str,
        model: str,
        storage: StorageConfig,
        display_name: str = "ACS Agent",
        ollama_url: str = "http://127.0.0.1:11434",
        api_base_url: str | None = None,
        force: bool = False,
    ) -> WorkspaceConfig:
        self.root.mkdir(parents=True, exist_ok=True)
        existing = [
            path for path in (self.config_path, self.genome_path, self.self_state_path) if path.exists()
        ]
        if existing and not force:
            names = ", ".join(path.name for path in existing)
            raise FileExistsError(f"workspace already contains {names}; use --force to replace config files")
        config = WorkspaceConfig(
            runtime_variant=runtime_variant,
            model=model,
            storage=storage,
            ollama_url=ollama_url,
            api_base_url=api_base_url,
        )
        genome = CharacterGenome(
            display_name=display_name,
            style_contracts=[
                "State reasons briefly when disagreeing.",
                "Separate remembered evidence from current inference.",
            ],
        )
        self_state = SelfState()
        _write_json_atomic(self.config_path, config.model_dump(mode="json"))
        _write_json_atomic(self.genome_path, genome.model_dump(mode="json"))
        _write_json_atomic(self.self_state_path, self_state.model_dump(mode="json"))
        return config

    def load_config(self) -> WorkspaceConfig:
        return WorkspaceConfig.model_validate_json(self.config_path.read_text(encoding="utf-8"))

    def load_genome(self) -> CharacterGenome:
        return CharacterGenome.model_validate_json(self.genome_path.read_text(encoding="utf-8"))

    def load_self_state(self) -> SelfState:
        return SelfState.model_validate_json(self.self_state_path.read_text(encoding="utf-8"))

    def resolved_filesystem_path(self, config: WorkspaceConfig | None = None) -> Path:
        config = config or self.load_config()
        value = config.storage.path
        if not value:
            raise ValueError("filesystem storage requires storage.path")
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.root / path
        return path.resolve()

    def write_export(self, payload: dict[str, Any], output: str | Path) -> Path:
        destination = Path(output).expanduser()
        if not destination.is_absolute():
            destination = self.root / destination
        destination = destination.resolve()
        _write_json_atomic(destination, payload)
        return destination
