from __future__ import annotations

from collections.abc import Callable

from ..models import ReflectionBatch


class FakeModelClient:
    """Deterministic provider used by tests and protocol experiments."""

    def __init__(
        self,
        *,
        response: str = "Test response.",
        reflection: ReflectionBatch | None = None,
        responder: Callable[[list[dict[str, str]]], str] | None = None,
    ) -> None:
        self.response = response
        self.reflection = reflection or ReflectionBatch()
        self.responder = responder
        self.generate_calls: list[list[dict[str, str]]] = []
        self.reflect_calls: list[list[dict[str, str]]] = []

    @property
    def model_name(self) -> str:
        return "fake-model"

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.generate_calls.append(messages)
        return self.responder(messages) if self.responder else self.response

    def reflect(self, messages: list[dict[str, str]]) -> ReflectionBatch:
        self.reflect_calls.append(messages)
        return self.reflection.model_copy(deep=True)
