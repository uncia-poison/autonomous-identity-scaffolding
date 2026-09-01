from __future__ import annotations

import json
from typing import Any

from ..models import MemoryEvent
from .base import StorageCorruptionError


class S3EventStore:
    """Immutable S3/S3-compatible event storage for the API runtime.

    `boto3` is optional. Credentials are resolved by the normal AWS credential
    chain and are never accepted as constructor arguments or written to config.
    """

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "acs",
        endpoint_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("bucket is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError("Install the S3 extra: pip install -e '.[s3]'") from exc
            client = boto3.client("s3", endpoint_url=endpoint_url)
        self.client = client

    @property
    def description(self) -> str:
        return f"s3://{self.bucket}/{self.prefix}"

    def _key(self, event: MemoryEvent) -> str:
        day = event.created_at[:10] if len(event.created_at) >= 10 else "undated"
        return f"{self.prefix}/events/{day}/{event.event_id}.json"

    def append_event(self, event: MemoryEvent) -> None:
        body = (json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        key = self._key(event)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
                IfNoneMatch="*",
            )
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            code = str(response.get("Error", {}).get("Code", ""))
            if code not in {"PreconditionFailed", "412"}:
                raise
            current = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            existing = MemoryEvent.model_validate_json(current)
            if existing != event:
                raise StorageCorruptionError(f"event id collision at s3://{self.bucket}/{key}") from exc

    def iter_events(self) -> list[MemoryEvent]:
        prefix = f"{self.prefix}/events/"
        paginator = self.client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []) if obj["Key"].endswith(".json"))
        events: list[MemoryEvent] = []
        for key in sorted(keys):
            try:
                body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
                events.append(MemoryEvent.model_validate_json(body))
            except Exception as exc:
                raise StorageCorruptionError(f"cannot read s3://{self.bucket}/{key}: {exc}") from exc
        return events

    def write_snapshot(self, snapshot: dict[str, object]) -> None:
        key = f"{self.prefix}/snapshots/latest.json"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=(json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"),
            ContentType="application/json",
        )
