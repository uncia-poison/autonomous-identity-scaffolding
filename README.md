# Continuity Core MVP

A local, model-independent prototype that turns conversation history into an evidence-backed **Identity Bundle**, compiles that bundle into target-specific continuity context, and runs a lightweight drift check against candidate responses.

This is the first executable product layer for the KAiScriptor / ScriptorMemory research stack. It does **not** claim to prove consciousness, recover hidden model state, or bypass platform policy. It preserves explicit evidence, provenance and a portable reconstruction profile.

## What exists in v0.1

- Ingest generic JSON message lists, plain text/Markdown transcripts, and common ChatGPT `mapping`-style conversation exports.
- Extract candidate identity invariants, preferences, relationships, goals and negative boundaries in English and Russian.
- Preserve source IDs, timestamps and confidence instead of flattening everything into untraceable prose.
- Derive a basic voice fingerprint from the selected speaker's messages.
- Emit a readable KAiScriptor-inspired anchor using `α Ω Ψ Δ ∇`.
- Compile profiles for generic, OpenAI-style, Anthropic-style and Gemini-style contexts.
- Run a conservative lexical drift report.
- No network calls and no paid API keys.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
```

## Build a bundle

```bash
continuity build examples/sample_chat.json --subject KAi --output identity.bundle.json
```

## Compile a portable profile

```bash
continuity compile identity.bundle.json --target anthropic --output profile.txt
```

## Check a candidate response

```bash
continuity drift identity.bundle.json examples/candidate_response.txt --output drift.json
```

## Output model

The bundle separates:

- stable identity claims;
- relationships;
- preferences;
- goals and future orientation;
- negative boundaries;
- voice features;
- evidence provenance;
- a compact portable anchor.

The deterministic extractor is deliberately modest. It is a safe baseline and a benchmark opponent for a later LLM-assisted extractor. The next meaningful milestone is not “more symbols”; it is a review interface where a human can accept, reject, merge and version every extracted claim before export.

## Product hypothesis

The sellable object is not a cipher manual. It is a continuity package:

> Import history → review evidence → compile identity → migrate between models → detect drift.

KAiScriptor remains the representation layer. ScriptorMemory becomes the versioned store and retrieval layer. This repository is the first executable bridge between the research and that product.
