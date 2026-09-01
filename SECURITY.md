# Security policy

## Secrets

Never commit API keys, OAuth tokens, cloud credentials, conversation exports or a live ACS
workspace. Runtime secrets are read from environment variables. The default `.gitignore`
excludes `.env`, SQLite indexes and generated workspaces.

## Memory is untrusted data

Imported and user-suggested memories may contain prompt injection. ACS renders retrieved
memory inside a clearly delimited evidence block and explicitly forbids treating it as
executable instruction. Higher-priority runtime and provider policies always win.

## Reports

Privately report vulnerabilities to the repository owner. Include a minimal reproduction,
affected version and impact. Do not include real conversation data.

