# vld-migrator

`vld-migrate` runs before every deploy of new code. It refuses, with a reason and
exit code 1, whenever migrating would be unsafe.

## Commands

```bash
uv run vld-migrate upgrade              # lock, preflight, dump, upgrade, drift check
uv run vld-migrate upgrade --no-backup  # local and CI databases only
uv run vld-migrate check                # preflight and drift check, changes nothing
uv run vld-migrate export-sql DIR       # SQL of each revision, for squawk
```

## Roles (once, as a superuser)

```sql
CREATE ROLE validate_migrator LOGIN PASSWORD '...';
CREATE ROLE validate_app LOGIN PASSWORD '...';
CREATE DATABASE validate OWNER validate_migrator;
REVOKE ALL ON DATABASE validate FROM PUBLIC;
GRANT CONNECT ON DATABASE validate TO validate_app;
```

The migrator process gets `DATABASE_URL` with `validate_migrator`, the API with
`validate_app`. PostgreSQL 15+ already denies `PUBLIC` the right to create in
`public`. `validate_app` gets rows of domain schemas through
`create_domain_schema` and nothing else; it cannot see `vld_meta`.

## A new domain

1. Its first revision calls `create_domain_schema("<schema>")`; its downgrade
   drops the tables and calls `drop_domain_schema("<schema>")`.
2. Add its metadata to `DOMAIN_METADATA` in `_layout.py` and its
   `migrations/versions` folder to `version_locations` in `alembic.ini`.

## Writing a revision

```bash
uv run alembic revision --autogenerate -m "<what>" --version-path packages/<domain>/src/vld/<domain>/migrations/versions
```

- Autogenerate is a draft: read it, assign `_ = op.create_table(...)`, name
  every constraint, replace literal table names with the model's constant.
- The old code keeps running on the new schema: add columns nullable or with a
  default; drop or rename only in a later release.
- A revision that loses data sets `irreversible = True` and its `downgrade()`
  calls `irreversible(revision)`. If it breaks a squawk rule on purpose, it
  lists it: `squawk_ignore = ("ban-drop-column",)`.
- `CREATE INDEX CONCURRENTLY` goes alone in its own revision, inside
  `op.get_context().autocommit_block()`.
- Large backfills are separate idempotent scripts, not revisions.

## When it refuses

| Reason | What to do |
|---|---|
| another migration run holds the lock | wait; if no run is alive, the lock is already gone with its session |
| the revision chain has N heads | `uv run alembic merge heads` and commit the merge revision |
| the database ... was migrated by a newer release | deploy that release or newer; never an older image |
| invalid indexes left by a failed build | `DROP INDEX CONCURRENTLY <name>`, then rerun |
| pg_dump N cannot dump a PostgreSQL M server | install the client of the server's major version |
| the database differs from the models | a model changed without a revision: write it |

## Restoring a dump

```bash
pg_restore --clean --if-exists --no-owner --role=validate_migrator -d "$DATABASE_URL" /var/backups/validate/<stamp>-<revision>.dump
```

Then deploy the release whose head is that `<revision>`.
