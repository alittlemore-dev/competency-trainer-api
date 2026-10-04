# Legacy Agent Access retirement

Personal API tokens use the ordinary editorial API and its explicit permissions. The private
certificate-based Agent API, local MCP bridge, machine-client management, and queue claims have
been retired.

Alembic revision `0021` removes only six Agent tables and four Agent enum types. Ordinary queued
questions and authored competency-matrix drafts retain their existing data. Historical revisions,
including `0012`, remain available to describe and test prior schema versions.

Downgrading `0021` recreates the empty legacy schema. It cannot recover deleted certificates,
machine-client records, claims, completion receipts, rotations, or audit events. Restoring that
history requires a database backup taken before the upgrade.

Generate future revisions against an isolated test database with the supported target:

```bash
MIGRATION_ENV_FILE=.env.test make revision message="describe change"
```

The target prepares dependencies, starts or reuses the configured test database, migrates it to the
current head, generates the revision, and cleans up only test resources it started. Without
`MIGRATION_ENV_FILE`, migration commands use the configured application database.

Existing local `.env.agent-bridge` files remain excluded from version control and Docker contexts
so retired local credential configuration cannot enter an image or commit. They have no runtime
consumer; remove them locally when no longer needed.
