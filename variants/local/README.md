# Local variant

This variant uses Ollama plus an external immutable event directory and a machine-local
rebuildable SQLite/FTS index. Generate a real workspace with:

```bash
acs --workspace ./agent-local init --variant local \
  --memory-root /mnt/gdrive/ACS/agent-memory --model qwen3:8b
```

Do not copy `acs.example.json` unchanged; its external path is illustrative.
