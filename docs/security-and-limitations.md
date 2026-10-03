# Security and limitations

## Trust boundaries

User text, imported archives, retrieved memories and model reflection are untrusted input.
Only the controller may assign system/tool provenance. Retrieved memory is delimited as data
inside the prompt, and higher-priority provider rules remain authoritative.

## Data protection

The event log stores redacted user and assistant turn text so the agent can inspect prior
outputs. The built-in redactor catches several common token/key formats, but it cannot
recognize every secret or personal datum. Do not paste credentials. Use encrypted private
storage, access controls, retention rules and backups appropriate to the conversation.

Environment variables and standard provider credential chains are used for API and S3
secrets. `.env` and local SQLite files are ignored by Git. Never commit a live agent
workspace.

## Prompt injection and memory poisoning

The gate blocks obvious secret material, high-imposition candidates and non-agent self claims,
but no deterministic filter is complete. Keep `memory review` under human control, validate
tool evidence before assigning `tool_derived`, and treat an unexpected burst of memory writes
as an incident.

## Operational limitations

- Filesystem/rclone storage is not a transactional multi-writer database.
- Lexical retrieval can miss paraphrases; replace it with a tested embedding retriever when
  the corpus grows, while keeping the event log canonical.
- Pressure detection and metrics are language- and pattern-dependent heuristics.
- A reflection call can fail. By default the visible response is retained, an alert is logged,
  and no model-proposed memory is written for that turn.
- Model/provider behaviour can change across versions; pin and record versions for research.
- S3 snapshots are mutable conveniences and must not be used as the only recovery source.

## Non-claims

AIS does not recover hidden sessions, grant the model undisclosed background execution, alter
weights, prove consciousness, or establish metaphysical personal identity. Continuity exists
only when the controller explicitly reloads external state and supplies selected evidence.

## Reporting vulnerabilities

Follow `SECURITY.md`. Do not publish private event logs, credentials or identifying transcripts
in an issue.
