from __future__ import annotations

from typing import Protocol

from ..models import ReflectionBatch


class ModelClient(Protocol):
    """Small provider boundary used by both ACS runtimes."""

    @property
    def model_name(self) -> str: ...

    def generate(self, messages: list[dict[str, str]]) -> str: ...

    def reflect(self, messages: list[dict[str, str]]) -> ReflectionBatch: ...
