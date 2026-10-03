# AIS naming and compatibility

The project is now **Autonomous Identity Scaffolding (AIS)**. Identity means the longitudinal
continuity of an agent's memories, principles, interests and revisions. It is broader than
an assigned role or a collection of personality traits.

## Preferred interfaces

- Distribution: `autonomous-identity-scaffolding`.
- Command: `ais`, or `python -m ais`.
- Public API: `from ais import IdentityGenome, IdentityRuntime`.
- Environment configuration: `AIS_MEMORY_ROOT`, `AIS_LOCAL_INDEX_ROOT`, `AIS_S3_BUCKET`,
  `AIS_S3_PREFIX` and `AIS_S3_ENDPOINT_URL`.

## Compatibility contract

The `acs` command and every existing `acs.*` Python import remain available. The new identity
types are aliases of `CharacterGenome` and `CharacterRuntime`; they refer to the same classes,
so existing objects and integrations keep working. The new `ais` package exposes the public
API and CLI; implementation submodules continue to use `acs.*` imports.

Existing `acs.json`, `character_genome.json`, `character_id` fields, `character_genome` export
keys, `acs.*.v1` schema identifiers and event payloads retain their current format. Existing
memory paths, object-store prefixes and local cache locations are not automatically moved.
There is no required event migration, directory rename or workspace reinitialization.

Each `AIS_*` environment variable takes precedence over its corresponding `ACS_*` variable.
If the new name is absent or empty, the old name is used. An explicitly configured workspace
continues to control its own storage settings; environment defaults are used during setup.

The former project name is retained in this compatibility record because older research,
integrations and repository links can refer to ACS.
