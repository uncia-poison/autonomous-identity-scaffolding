# Memory governance

## Provenance

| Origin | Meaning | Who may legitimately create it |
| --- | --- | --- |
| `agent_proposed` | The model endorses a compact post-turn conclusion | Structured reflection |
| `user_suggested` | The user asserted or requested the record | User/CLI or reflection source labelling |
| `system_observed` | The controller observed an operation | Runtime only |
| `tool_derived` | A configured tool returned supporting evidence | Tool integration only |
| `imported_archive` | A migration extracted it from older material | Importer only |

The runtime normalizes a reflection that tries to claim system, tool or archive provenance.
User-origin self-principles and goals are queued for review; they never become self-authored by
being phrased as a command.

## Gate outcomes

- `write`: quality threshold passed and policy allows the type/origin combination.
- `merge`: a near-duplicate corroborates an existing active memory.
- `revise`: an agent proposal explicitly targets an existing memory with adequate stability
  and confidence.
- `review`: the candidate may be useful but needs an operator decision.
- `reject`: low salience, excessive imposition risk, secret-like content or another hard rule.

All outcomes are events. Rejected candidates therefore remain auditable without being
retrieved as durable memories.

Reflection interest updates are converted to `self_interest` candidates first. The project is
activated only if that candidate passes the same gate. Durable `current_goals` and
`recent_lessons` in self-state are derived from accepted memory entries rather than trusted as
an alternate write channel.

## Review workflow

```bash
acs --workspace ./kai memory review
acs --workspace ./kai memory approve cand_ab12cd34 --reason "Verified against the archive"
acs --workspace ./kai memory reject cand_ef56ab78 --reason "User-imposed identity claim"
```

Approval records the operator action. It does not relabel a user-suggested or imported claim
as agent-authored.

## Correction workflow

A model correction sets `target_memory_id`. An operator can also revise or retract:

```bash
acs --workspace ./kai memory history mem_ab12cd34
acs --workspace ./kai memory revise mem_ab12cd34 \
  "Revised conclusion" --reason "New evidence E-17"
acs --workspace ./kai memory retract mem_ab12cd34 --reason "Finding was falsified"
```

History contains every prior semantic version. `memory.use` updates use counters but does not
create a semantic revision. A physical erasure is intentionally outside the ordinary command
surface.

## Genome changes

The character genome is assigned configuration, not self-authored memory. Runtime code may
record `genome.revision_proposed`, but it does not apply it automatically. Review and edit
`character_genome.json` with normal configuration change control.
