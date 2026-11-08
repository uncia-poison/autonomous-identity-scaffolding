# Identity conclusion ledger

AIS keeps raw memory and durable inference separate.

A memory answers **what was observed or recorded**. A conclusion answers **what the agent
currently infers from one or more observations**. Identity continuity needs both: otherwise a
single summary can silently turn an old interpretation into an apparent fact.

## Rules

1. Conclusions are append/revise/retract events in the same immutable event stream.
2. Provenance is preserved. User-suggested text never becomes agent-authored by relabeling.
3. Every conclusion may cite evidence, counterevidence and other dependencies.
4. Revision preserves prior versions.
5. A stale conclusion is excluded from the active view but kept for audit and later review.
6. High identity relevance means "review carefully", not "make immutable".
7. Self-identity is reconsolidated from supported conclusions; it is never destructively
   rewritten from one surprising turn.

## Event types

- `conclusion.add`
- `conclusion.revise`
- `conclusion.mark_stale`
- `conclusion.review`
- `conclusion.retract`

The dependency IDs are intentionally opaque to AIS. They can refer to memory IDs, earlier
conclusions, external evidence receipts or continuity records. A separate dependency/impact
layer may use them to determine which conclusions require review after upstream change.
