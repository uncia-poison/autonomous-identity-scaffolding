from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..models import ReflectionBatch


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    """Native Ollama client with schema-constrained post-turn reflection."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 180.0,
        temperature: float = 0.65,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    @property
    def model_name(self) -> str:
        return self.model

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, object] | None = None,
        temperature: float | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature if temperature is None else temperature},
        }
        if response_format is not None:
            payload["format"] = response_format
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise OllamaError(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc
        try:
            return str(body["message"]["content"]).strip()
        except (KeyError, TypeError) as exc:
            raise OllamaError(f"Unexpected Ollama response: {body!r}") from exc

    def generate(self, messages: list[dict[str, str]]) -> str:
        return self._chat(messages)

    def reflect(self, messages: list[dict[str, str]]) -> ReflectionBatch:
        content = self._chat(
            messages,
            response_format=ReflectionBatch.model_json_schema(),
            temperature=0.0,
        )
        try:
            return ReflectionBatch.model_validate_json(content)
        except Exception as exc:
            raise OllamaError(f"Ollama reflection did not match the ACS schema: {exc}") from exc
