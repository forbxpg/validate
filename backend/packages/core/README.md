# vld-core

Shared kernel of every domain: settings, the database kit, Redis, rate limits,
logs, the audit log and the dependency-injection provider. It knows no domain and
no HTTP: an import-linter contract forbids `vld.web`, FastAPI and Starlette here,
so the worker and the command lines use it as they are.

## What's inside

```
config/        settings from the environment, one class per concern
database/      engine and sessions, metadata with a naming convention, mixins,
               PostgreSQL enums, integrity checks, the unit of work
ratelimit/     fixed-window rate limiter on Redis
audit/         append-only audit log: port, reader, tables and their migration
pagination/    page contracts without the HTTP layer
obs/           structlog and Sentry setup
di.py          CoreProvider: settings, engine, sessions, unit of work, audit, Redis
```

## `config/` — settings

Each concern is a `pydantic-settings` class with its own prefix, read from the
environment or `.env`. `.env.example` lists every variable.

| Class | Variables | Required |
|---|---|---|
| `AppSettings` | `APP_ENV`: `local`, `test` or `production` (default) | — |
| `DatabaseSettings` | `DATABASE_URL`, `DATABASE_ECHO`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT`, `DATABASE_POOL_PRE_PING`, `DATABASE_POOL_RECYCLE` | `DATABASE_URL` |
| `RedisSettings` | `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_USERNAME`, `REDIS_PASSWORD` | `REDIS_HOST` |
| `CorsSettings` | `MIDDLEWARE_CORS_ALLOWED_ORIGINS`: a JSON list | yes |
| `ObservabilitySettings` | `LOG_LEVEL`, `LOG_JSON`, `SENTRY_DSN` | — |

Required settings have no defaults on purpose: a process with a missing variable
fails at startup instead of coming up against localhost. A domain declares its
own settings with `settings_config("PREFIX_")`.

## `database/` — the database kit

- `create_engine(settings)` and `create_session_factory(engine)`: the async
  engine on asyncpg and a factory of `AsyncSession`.
- `make_metadata(schema)` gives each domain its own PostgreSQL schema;
  `NAMING_CONVENTION` names every index and constraint (`ix_…`, `uq_…`, `ck_…`,
  `fk_…`, `pk_…`), so migrations and error checks can refer to them by name.
- Mixins: `UUIDPkMixin` (uuid4 from the application, `gen_random_uuid()` as the
  server default) for business entities, `BigIntPkMixin` for append-only tables
  such as logs and the outbox, `TimestampMixin` (`created_at`, `updated_at`) and
  `CreatedAtMixin`.
- `PostgresEnum(enum_cls, name, metadata=...)`: a native PostgreSQL enum whose
  labels are the values of a `StrEnum`.
- `is_unique_violation(exc, name)` and `is_foreign_key_violation(exc, name)`:
  tell which named constraint refused a write, so a race on a unique email turns
  into a domain error instead of a 500.
- `UnitOfWork` is the port of the transaction boundary (`commit`, `rollback`,
  `flush`); `SqlAlchemyUnitOfWork` implements it over the request session.

## `ratelimit/` — rate limits

`RateLimiter(redis).hit(key, limit, window_ms)` counts attempts in a fixed
window with one Lua script. Over the limit it raises `RateLimitExceededError`
with the seconds to wait; when Redis does not answer, `RateLimiterUnavailableError`.
Whether to refuse or let the request through when Redis is down is decided by the
caller (see `vld.web.throttling`).

## `audit/` — the audit log

Domains record what matters — logins, password changes, role changes, deleted
accounts — through the `AuditLog` port, in their own transaction:

```python
await audit.record(
    AuditEntry(
        action=AuditAction.PASSWORD_CHANGED,
        actor_id=user.id,
        target_id=user.id,
    ),
)
```

- `AuditAction` lists the actions; an entry carries the actor, the target and a
  payload of strings, and knows nothing about the domain that wrote it.
- `AuditQuery.search(...)` reads pages filtered by actor, target and time;
  `AuditRecord` and `AuditPage` are what it returns.
- The table lives in its own `audit` schema and is append-only: the migration
  revokes `UPDATE`, `DELETE` and `TRUNCATE` from the API role and adds triggers
  that refuse them anyway.
- `AUDIT_METADATA` joins the metadata the migrator manages.

## `pagination/` — page contracts

`Page` and `PageParams` are protocols, so `core` stays free of
`fastapi-pagination`; `Projection` says what a caller wants to see and
`transformer(mapper, project)` turns ORM rows into domain objects and then into
that projection. The HTTP page types live in `vld.web.pagination`.

## `obs/` — logs and errors

- `configure_logging(settings)` sets up structlog and the standard logging on
  stdout: JSON lines with `LOG_JSON=true` (the default), readable lines otherwise.
- `configure_sentry(settings)` turns error tracking on when `SENTRY_DSN` is set,
  without personal data and without local variables.

## `di.py` — the provider

`CoreProvider` gives every process the same infrastructure through dishka:

| Scope | Provides |
|---|---|
| app | `AppSettings`, `DatabaseSettings`, `RedisSettings`, `AsyncEngine`, `async_sessionmaker`, `Redis` |
| request | `AsyncSession`, `UnitOfWork`, `AuditLog`, `AuditQuery` |

`CONTAINER_VALIDATION` is the validation the containers of the API and the worker
share.

## Tests

```bash
uv run pytest packages/core
TEST_REDIS_URL=redis://localhost:6379/15 uv run pytest -m integration packages/core
```

Unit tests: settings, metadata and mixins, the unit of work, the rate limiter,
logging and the provider. The integration test runs the limiter against a live
Redis.
