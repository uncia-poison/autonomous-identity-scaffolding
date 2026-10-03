# Source lineage

AIS v0.3 consolidates design ideas from the repository's earlier Continuity Core MVP and from
related experiments inspected during the architecture review. Ideas were translated into a
neutral, auditable implementation; source-specific identity claims were not copied into the
core.

| Source family | Retained idea | AIS treatment |
| --- | --- | --- |
| Continuity Core v0.1 | Transcript ingestion, evidence extraction, portable profile, lexical drift check | Preserved as the `continuity_core` compatibility package |
| KAiScriptor | Compact `α Ω Ψ Θ Δ Ξ ∇` anchor | Explicit export/prompt representation only; no hidden persistence claim |
| ScriptorMemory / kai-graph-bio | Durable key/sequence memory and recall | Replaced with typed event sourcing, provenance, gating and revision history |
| SKAi | Multi-stage turn cycle and self-authored state files | Reduced to stance → response → reflection → gate → event replay |
| ontodiff | Self-write gate and JSON persistence | Extended with typed scoring, review, merge/revision and immutable audit events |
| ThreadWeave | Cross-session carryover tickets | Represented by interests, recent turns and explicit external replay |

Project planning and field-definition documents supplied with the work informed the split
between a neutral framework and a longitudinal KAi case. They are not redistributed here
because the repository is intended to contain the executable neutral core and its public
documentation.

Where this document says “inspired by,” it denotes architectural lineage, not API compatibility
or a claim that experimental prototypes already implemented the current guarantees.
