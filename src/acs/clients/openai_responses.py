from __future__ import annotations

import os
from typing import Any

from ..models import ReflectionBatch


class OpenAIResponsesClient:
    """Stateless OpenAI Responses client; canonical memory stays outside OpenAI."""

    def __init__(
        self,
        model: str = "gpt-5-mini",
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 180.0,
        client: Any | None = None,
    ) -> None:
        self.model = model
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "Install the API extra: pip install 'autonomous-character-scaffolding[api]'"
                ) from exc
            kwargs: dict[str, Any] = {
                "api_key": api_key or os.getenv("OPENAI_API_KEY"),
                "timeout": timeout,
            }
            if base_url:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
        self.client = client

    @property
    def model_name(self) -> str:
        return self.model

    def generate(self, messages: list[dict[str, str]]) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=messages,
            store=False,
        )
        text = str(response.output_text or "").strip()
        if not text:
            raise RuntimeError("OpenAI Responses returned no output text")
        return text

    def reflect(self, messages: list[dict[str, str]]) -> ReflectionBatch:
        response = self.client.responses.parse(
            model=self.model,
            input=messages,
            store=False,
            text_format=ReflectionBatch,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI structured reflection returned no parsed output")
        return parsed
