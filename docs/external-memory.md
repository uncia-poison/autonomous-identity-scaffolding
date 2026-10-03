# External memory backends

## Recommended layouts

Keep configuration and canonical memory separate:

```text
./kai-local/
  acs.json
  character_genome.json
  self_state.json

/mnt/gdrive/AIS/kai-memory/
  events/YYYY-MM-DD/evt_*.json
  snapshots/latest.json
```

The local SQLite/FTS index is deliberately outside this tree. A snapshot may be overwritten
and an index may be deleted; events are the source of truth.

## Google Drive, Dropbox, OneDrive and rclone

AIS only needs a directory interface. Point `--memory-root` at a desktop-sync folder or an
`rclone mount` target. With rclone, create and test the remote first, use your own OAuth client
where the provider recommends it, and enable encryption with `rclone crypt` when appropriate.

Consumer sync clients are eventually consistent. Safe operating rules:

- one active writer per agent workspace;
- let sync finish before moving the writer to another machine;
- never edit event JSON in place;
- resolve a duplicate/conflicted event by retaining both differently named valid events, then
  inspect replay; never merge JSON text by hand;
- back up the complete `events/` directory before a migration.

Multiple readers are fine. For simultaneous server writers, prefer the S3-compatible backend
and serialize turns for one agent at the application layer.

## S3 and compatible object stores

The S3 layout mirrors the filesystem layout under the configured prefix. Each event uses an
independent object key and a conditional create. Configure credentials through the SDK's
standard environment, profile, instance-role or workload-identity chain. Do not put access
keys in `acs.json`.

## Encryption, retention and recovery

- Encrypt the volume/remote and transport.
- Treat turn events as personal conversation history.
- Restrict file or bucket access to the agent controller and its operator.
- Use provider versioning/backups and test restoration.
- Use `memory retract` for semantic correction. If law or safety requires physical deletion,
  remove the affected objects and backups through an explicit, separately audited process;
  ordinary AIS commands intentionally preserve lineage.

Recovery is deterministic: restore event files, point a new workspace at them, and run
`ais ... inspect`. The current ledger and local index are rebuilt from the event stream.
