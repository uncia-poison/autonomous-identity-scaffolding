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
7. Model-proposed identity conclusions enter review. Only a trusted caller can approve
   a specific revision. The runtime does not automatically replace self-state from a single turn.
8. Automatic writes of ordinary agent conclusions require references to recalled records.
   Revised, merged, archived or retracted records move dependent conclusions into review
   during event replay. The current context receives at most eight active conclusions.

## Event types

- `conclusion.add`
- `conclusion.revise`
- `conclusion.mark_stale`
- `conclusion.review`
- `conclusion.retract`

AIS tracks dependencies between stored IDs. External receipts may be recorded by a trusted
caller, which is responsible for verifying their authority. The AIS ledger supplies an active
projection to Kai. A host implementing the SKAi contract can use ontodiff for wider self-state
review, including policies and intentions.

List pending conclusions with `ais conclusion pending`. Inspect the origin, evidence
and revision before approving with
`ais conclusion approve CONCLUSION_ID --revision N --reason "Evidence reviewed"`.
Use `reject` with the same arguments to retract a proposal. Approval preserves the
original origin, and the review event separately records who performed the review.
