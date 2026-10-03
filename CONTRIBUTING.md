# Contributing

Contributions should preserve five invariants:

1. No consciousness or weight-update claims without independent evidence.
2. Every durable write has provenance and an immutable audit event.
3. User-suggested memory is never relabeled as agent-authored.
4. Disagreement policy must not become automatic opposition.
5. Neutral AIS core stays separate from personal case layers.

Run `pytest` and `ruff check src tests` before proposing a change. New storage backends need
round-trip, duplicate-event and corruption tests. New metrics must document what they measure
and what they do not measure.

