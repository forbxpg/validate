# vld-api

The HTTP API process: a FastAPI application and its composition root. It holds
no business logic; it connects the domains, the shared HTTP layer and the
infrastructure, and adds the probes an orchestrator needs.

## Run

```bash
cd backend
cp .env.example .env          # once; fill in what the stand needs
uv run uvicorn vld.api.main:create_app --factory --reload
```

`create_app` is a factory: settings are read when the process starts, not when
the module is imported. Behind a reverse proxy, run uvicorn with
`--proxy-headers` so that `vld.web.throttling` sees the client address.

Required variables (the process refuses to start without them):
`DATABASE_URL`, `REDIS_HOST`, `MIDDLEWARE_CORS_ALLOWED_ORIGINS` and those of the
domains, such as `JWT_SECRET_KEY` of auth. `.env.example` lists all of them.

## What's inside

```
main.py        create_app(): logs and Sentry, the container, domains, middleware
_health.py     GET /health and GET /ready
```

## Composition

`create_app()` does, in this order:

1. configures logging and Sentry from `ObservabilitySettings`;
2. builds the dishka container from `CoreProvider`, `ThrottlingProvider` and the
   providers of every domain;
3. mounts the probes at the root and every domain under `/api/v1` with
   `vld.web.mounting.mount` (error handlers, the access-marker check, the Origin
   check);
4. adds `RequestIdMiddleware` and CORS: the origins of
   `MIDDLEWARE_CORS_ALLOWED_ORIGINS`, with credentials, and `X-Request-Id`
   readable by the browser.

On startup the lifespan runs the `on_startup` check of each domain, so a
misconfiguration fails the start instead of the first request; on shutdown it
closes the container.

The domains served are listed in one place:

```python
DOMAINS: tuple[DomainDescriptor, ...] = (AUTH_DOMAIN,)
```

A new domain is one more `DomainDescriptor` here and a dependency in
`pyproject.toml`; its routes, errors and providers come with the descriptor.

## Probes

| Route | Answers |
|---|---|
| `GET /health` | `200 {"status": "ok"}` while the process runs; touches no dependency |
| `GET /ready` | `200` when PostgreSQL and Redis both answer within 2 s, `503` otherwise, with the result of each: `{"status": "not_ready", "database": true, "redis": false}` |

A failed readiness check is logged as `readiness_check_failed` with the name of
the dependency.

## Tests

```bash
uv run pytest apps/api
TEST_DATABASE_URL=... TEST_REDIS_URL=... uv run pytest -m integration apps/api
```

The unit tests build the application against unreachable dependencies:
liveness, readiness answering 503, the CORS preflight for a trusted and a
foreign origin, and `X-Request-Id` exposed to the browser. The integration test
checks readiness answering 200 against a live PostgreSQL and Redis.
