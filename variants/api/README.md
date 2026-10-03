# API variant

This variant uses OpenAI Responses with `store=False`. The controller reloads filesystem or
S3-compatible events before each request, retrieves a bounded context and records the visible
response plus structured reflection externally.

```bash
ais --workspace ./agent-api init --variant api \
  --memory-root /mnt/gdrive/AIS/agent-api-memory --model gpt-5-mini
```

For S3, use `--storage s3 --s3-bucket ... --s3-prefix ...` and the standard AWS credential
chain. The example files contain no secrets.
