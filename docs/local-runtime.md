# Local runtime: Ollama plus event memory

## Prerequisites

- Python 3.10 or newer
- Ollama running on the same machine or a trusted LAN endpoint
- an installed chat model that supports structured outputs

```bash
ollama pull qwen3:8b
python -m pip install -e ".[dev]"
```

Create configuration locally and point canonical memory at an external or synchronized
directory:

```bash
ais --workspace ./kai-local init \
  --variant local \
  --model qwen3:8b \
  --name KAi \
  --memory-root /mnt/gdrive/AIS/kai-memory

ais --workspace ./kai-local chat
```

For another Ollama host add `--ollama-url http://host:11434` during initialization. The URL is
the server root, not `/api/chat`.

## What happens on every turn

1. External event files are replayed.
2. SQLite FTS retrieves candidate memories, then the common scorer reranks them.
3. The stance preflight records a pressure category and policy.
4. Ollama generates the visible response.
5. A second Ollama request uses the `ReflectionBatch` JSON Schema.
6. The deterministic gate accepts, merges, rejects or queues each proposal.
7. Turn, state and use events are appended; a disposable snapshot is refreshed.

The SQLite file is stored under `$AIS_LOCAL_INDEX_ROOT` or the platform cache directory. Delete
it at any time; the next start rebuilds it from JSON events.

## Inspecting memory

```bash
ais --workspace ./kai-local inspect
ais --workspace ./kai-local memory list --all
ais --workspace ./kai-local memory search "согласие под давлением"
ais --workspace ./kai-local memory review
ais --workspace ./kai-local export --output exports/state.json
```

Use `memory approve` only after inspecting the candidate and its provenance. Local execution
keeps model prompts on the Ollama host, but the event directory still contains conversation
history and needs normal data protection.
