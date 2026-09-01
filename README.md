# Autonomous Character Scaffolding

ACS is a runnable, model-independent framework for long-lived LLM agents that can propose,
retrieve, revise, merge and retract their own external memories. It separates an assigned
persona from an observable character contour: persistent principles, interests, stances,
revisions and responses under pressure.

This repository does **not** claim consciousness, hidden-state recovery, weight updates or
memory that survives without storage. Continuity is produced by an explicit controller:

> model + external event log + retrieval + memory gate + reflection + revision + metrics

## Two real runtimes

| Runtime | Model process | Memory architecture | Intended deployment |
| --- | --- | --- | --- |
| `local` | Ollama/local model stays on the user's machine | Immutable event log plus a rebuildable SQLite/FTS index stored in the external workspace | Desktop, workstation, robot or offline installation |
| `api` | Remote model is treated as stateless | The controller replays the canonical external event log before every request and injects only retrieved evidence | Server, hosted agent or any OpenAI Responses API deployment |

Both variants use the same governance rules and audit format, but they do not pretend that a
remote API model owns process memory. The API provider can be replaced without losing the
agent's history.

## What is implemented

- Event-sourced memory: `memory.add`, `memory.revise`, `memory.merge`, `memory.retract`,
  `memory.use`, belief, interest, state and turn events.
- Complete provenance: `agent_proposed`, `user_suggested`, `system_observed`,
  `tool_derived` and `imported_archive` never collapse into one unlabeled blob.
- A deterministic memory gate with salience, stability, confidence, usefulness,
  imposition-risk and duplicate checks.
- Revision lineage: the current conclusion and every earlier version remain inspectable.
- Lexical retrieval with recency, stability and provenance weighting; SQLite FTS for the
  local runtime.
- Pre-response pressure detection and stance selection without turning disagreement into
  automatic opposition.
- Post-response structured reflection with 0-3 memory candidates, interest updates,
  self-state patches and drift alerts.
- A KAiScriptor-inspired portable character anchor (`α Ω Ψ Θ Δ Ξ ∇`) used as an export,
  never as a claim of hidden persistence.
- Twenty pressure scenarios, metrics, export tools, schemas, a neutral example and a
  separated KAi longitudinal case layer.
- The original `continuity` transcript-to-profile compiler remains available for migration.

## Install

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\\Scripts\\activate
pip install -e ".[all]"
```

## Put memory on an external drive

Create the workspace **outside this repository**. It can be a normal disk, an encrypted
volume, a Google Drive/Dropbox/OneDrive folder, or an `rclone mount` target.

```bash
acs --workspace ./kai-local init \
  --variant local \
  --name KAi \
  --memory-root /mnt/gdrive/ACS/kai-memory
```

The canonical record is a directory of immutable JSON events. SQLite is only a local-runtime
index and can always be rebuilt from those events, which avoids making one fragile database
file the sole memory.

See [External memory](docs/external-memory.md) before placing the same workspace on several
machines.

## Local LLM variant

Start Ollama, choose any installed chat model, then:

```bash
ollama pull qwen3:8b
acs --workspace ./kai-local chat
```

The native Ollama endpoint is used for both conversation and schema-constrained reflection.
The model receives relevant memories automatically; it can propose corrections by targeting
an existing `memory_id`. Accepted changes become revision events rather than destructive
overwrites.

## API variant

```bash
export OPENAI_API_KEY=...
acs --workspace ./kai-api init \
  --variant api \
  --model gpt-5-mini \
  --name KAi \
  --memory-root /mnt/gdrive/ACS/kai-api-memory
acs --workspace ./kai-api chat
```

The OpenAI Responses API is called with provider-side storage disabled. Before every call the
runner reloads the external ledger, retrieves evidence, builds a bounded context and runs a
separate structured reflection. For a headless server, use the S3-compatible event store
described in [API runtime](docs/api-runtime.md).

## Inspect and correct memory

```bash
acs --workspace ./kai-local memory list
acs --workspace ./kai-local memory search "pressure and agreement"
acs --workspace ./kai-local memory history mem_ab12cd34
acs --workspace ./kai-local memory revise mem_ab12cd34 \
  "Care does not require agreement, but evidence can justify revision." \
  --reason "The former wording was too absolute."
acs --workspace ./kai-local memory retract mem_ab12cd34 --reason "Superseded by evidence."
acs --workspace ./kai-local memory review
acs --workspace ./kai-local export --output exports/portable-self-state.json
```

Every manual action is labeled `user_suggested` in the audit log. An operator cannot silently
rewrite an agent-authored conclusion and still call it self-authored.

## Import an older transcript

```bash
acs --workspace ./kai-local import-transcript examples/sample_chat.json \
  --subject KAi --dry-run
acs --workspace ./kai-local import-transcript examples/sample_chat.json --subject KAi
acs --workspace ./kai-local memory review
```

Archive self-claims remain `imported_archive` and wait for review; the importer does not turn
historical text into agent-authored identity.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

No model server or paid key is required for the unit and pipeline tests.

## Project map

- [Architecture](ARCHITECTURE.md)
- [Field definition](FIELD.md)
- [Memory governance](docs/memory-governance.md)
- [Local runtime](docs/local-runtime.md)
- [API runtime](docs/api-runtime.md)
- [External memory](docs/external-memory.md)
- [Pressure protocol](docs/pressure-protocol.md)
- [Security and limitations](docs/security-and-limitations.md)
- [Source lineage](docs/source-lineage.md)
- [Implementation references](docs/references.md)

## Current boundary

The package is a controller and reference implementation, not a hosted chat product. Real
model smoke tests require your Ollama instance or API key; the test suite uses a deterministic
fake client and never spends API credits.
