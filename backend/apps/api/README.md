# vld-api

The HTTP API process: a FastAPI application and its composition root. It holds
no business logic; it connects the domains, the shared HTTP layer and the
infrastructure, and adds the probes an orchestrator needs.

## Run

On the stand the API runs in its container (`make dev`, see
[infrastructure/README.md](../../../infrastructure/README.md)). On the host:

```bash
cd backend
uv run --env-file .env vld-api run --reload       # http://127.0.0.1:8000
uv run vld-api run --help
```

`vld-api run` takes `--host`, `--port`, `--reload`, `--workers` and
`--forwarded-allow-ips`, and serves the `create_app` factory: settings are read
when the process starts, from the environment only. Behind a reverse proxy,
list the proxy in `--forwarded-allow-ips` so that `vld.web.throttling` sees the
client address. The image runs `vld-api run --host 0.0.0.0 --port 8000`.

Required variables (the process refuses to start without them):
`DATABASE_URL`, `REDIS_HOST`, `MIDDLEWARE_CORS_ALLOWED_ORIGINS` and those of the
domains, such as `JWT_SECRET_KEY` of auth. `.env.example` lists all of them.

## What's inside

```
cli.py         vld-api run: uvicorn over the create_app factory
main.py        create_app(): logs, Sentry, metrics, the container, domains, middleware
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

## Metrics

`GET /metrics` is for Prometheus: requests by route template, method and status
class, and latency histograms, from `prometheus-fastapi-instrumentator`. The
probes and `/metrics` itself are not counted. The reverse proxy must not
publish this route. Each application has its own registry, so run one process
per container (`--workers 1`) and scale with containers.

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
