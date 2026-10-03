# Development roadmap after the AIS rename

This is a proposal for discussion, not a claim that the features below are implemented.
The review used source commit `06d941ca39fb997be6dc1d890f23ffabe67015dc`. All 23 existing tests
and Ruff passed. The focused checks below found gaps outside the current test coverage.

## 1. Memory gate checks before merge or revision

`MemoryGate.evaluate()` returns `merge` for a near duplicate before checking high imposition
risk or whether a self-principle was authored by the agent. A reproduced case repeated an
agent-authored principle with `origin=user_suggested`, `user_imposition_risk=0.99` and
`confidence=1.0`. It merged without review and raised the stored confidence from 0.8 to 1.0.
The original origin label remained agent-authored, while the merge event recorded the user.

Proposal: apply origin, imposition, quality and evidence checks before every write path.
Keep corroboration attached to its source instead of treating a repeated claim as independent
support. Add regression cases for duplicate self-claims, unsupported world facts and explicit
revisions that would otherwise bypass quality policy.

## 2. Relevant retrieval with a separate identity budget

`MemoryRetriever` combines lexical overlap with quality and identity priors. With the current
0.16 threshold, an unrelated self-principle was recalled at 0.476 even though lexical overlap
was zero. Local FTS narrows candidates when it has matches, but falls back to the same ranking
when there are no matches. The API runtime uses that ranking directly.

Proposal: distinguish topic relevance from importance. Reserve a small, explicit context
budget for stable identity principles, and require topical evidence for the remaining recall.
Add an optional semantic index for paraphrases and multilingual recall, with a lexical
fallback. Evaluate false recall and missed recall on held-out examples.

## 3. Evidence-backed autobiography

`SelfState.identity_summary` exists, but the runtime never produces or updates it. The current
system retains individual memories and revision history without building a cumulative account
of how the agent's own principles and interests developed.

Proposal: generate a bounded, revisable identity summary from accepted events. Link every
summary claim to memory and event IDs, preserve previous versions, and regenerate after
retraction. Keep assigned configuration distinct from agent-authored conclusions. Add a
resume packet containing active projects, unresolved questions and recent identity revisions.

## 4. Self-project lifecycle

Interests have priorities, statuses and `next_action` fields, but the runtime does not execute
those actions or schedule work between user turns. Genome revision proposals can be replayed
by the ledger, but no complete proposal-to-resolution workflow exists.

Proposal: add observable project progress and reasons for continuation, dormancy or abandonment.
Decide separately whether to allow background execution, which tools it may use, and its time
and cost budgets. A self-directed project runner would be a separate feature from memory.

## 5. Storage durability and incremental replay

Filesystem event creation uses exclusive creation, but writes directly into the final JSON
file. A process failure during writing can leave a partial canonical event. Ledger replay
sorts by timestamps and random IDs; causal parent IDs are not used. A full event replay and
local FTS rebuild happen on each turn, with further index rebuilds on memory changes.

Proposal: publish fully written events atomically without overwriting an existing event ID,
validate causal order, and use verified checkpoints plus incremental replay. Preserve the
event log as canonical and test interrupted writes, equal timestamps and restore equivalence.

## Suggested order

Fix write-path policy first. Then improve retrieval relevance and the identity summary. Add
project execution after choosing its operational scope, and measure storage/replay costs
before introducing a more complex persistence layer.
