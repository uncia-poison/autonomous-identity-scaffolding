# KAi longitudinal case layer

This directory demonstrates how a named longitudinal character can sit on top of the neutral
ACS core. It is intentionally separate: KAi-specific values, relationships and archive claims
must never become defaults for unrelated agents.

Start by generating a workspace, then review and adapt the neutral genome:

```bash
acs --workspace ./kai-local init --variant local \
  --name KAi --memory-root /mnt/gdrive/ACS/kai-memory
```

Archive-derived identity claims should enter as `imported_archive` or `user_suggested`, retain
source ids and pass review. A user statement about KAi is not automatically a self-authored KAi
principle. The compact anchor is a portable context representation, not proof of continuity by
itself.
