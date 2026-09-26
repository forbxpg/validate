# infrastructure

The local stand of validate in Docker: the applications built from their
Dockerfiles, what they need, and an optional observability stack. It is run
through the `Makefile` at the repository root.

## Start

```bash
cp backend/.env.example backend/.env     # once
make dev                                 # the stand in the foreground, code synced
make dev WITH="grafana prometheus loki"  # with optional services
make dev WITH=obs                        # with all of them
```

`make dev` builds the images, starts Postgres, Redis and RabbitMQ, runs the
migrator once, then the API and the worker, and watches the code: a change in
`backend/packages` or `backend/apps/api/src` reaches the API, which reloads; a
change in the worker restarts it; a change of `uv.lock` rebuilds the image.
`make up` does the same in the background; `make help` lists every target.

## Services and ports

Everything is published on `127.0.0.1` only, on ports away from the defaults, so
the stand runs next to other projects. Inside the network services use their
usual ports and names (`postgres:5432`, `redis:6379`, …).

| Service | When | Address |
|---|---|---|
| API | always | http://localhost:8010 (`/health`, `/ready`, `/docs`, `/metrics`) |
| Postgres 18 | always | `localhost:5452`, superuser `postgres` / `postgres` |
| Redis 8 | always | `localhost:6399` |
| RabbitMQ 4 | always | `localhost:5692`, UI http://localhost:15692 (`validate` / `validate`) |
| migrator | always, once before the API and the worker | — |
| worker | always | metrics on `worker:9100` inside the network |
| Mailpit | `APP_ENV=local` in `backend/.env` | http://localhost:8035, SMTP `localhost:1035` |
| Prometheus, postgres and redis exporters | `WITH=prometheus` | http://localhost:9092 |
| Loki and Alloy | `WITH=loki` | `localhost:3102`; read the logs in Grafana |
| Grafana | `WITH=grafana` | http://localhost:3002, open read-only; admin / admin to edit |
| GlitchTip | `WITH=glitchtip` | http://localhost:8036 |

## Database roles

`initdb/01-roles.sql` creates the roles of production: `validate_migrator` owns
the database and its schemas, `validate_app` is what the API and the worker use.
A missing grant shows up on the stand, not after a deploy. The migrator runs
with `--no-backup`: the dump before an upgrade belongs to deploys.

`initdb/` runs only on an empty volume. After editing it, or to start from
scratch: `make reset` (deletes the volumes of the stand) and `make up`.

## Configuration

The containers read `backend/.env` and then take the in-network addresses from
`compose.yaml`; `.env` itself keeps the published ports for the tests and for
`make api-host`, which stops the API container and runs the API on the host
with `--reload` for a debugger. `ENV_FILE=path` makes the Makefile use another
file.

## Observability

- **Prometheus** scrapes the API (`/metrics`: requests, statuses, latency by
  route), the worker (outbox rows, letters by outcome, time to send), RabbitMQ
  (its own plugin, queue depth by name), Postgres and Redis.
- **Loki** gets the logs of this project's containers through Alloy, and no one
  else's; labels are `service` and `container`, the JSON fields are parsed in
  queries: `{service="api"} | json | event="..."`.
- **Grafana** comes with both datasources and two dashboards in the `validate`
  folder: the API, and the worker with RabbitMQ.
- **GlitchTip** collects the errors the applications send through Sentry. Once:
  sign up at http://localhost:8036, create an organization and a project, copy
  its DSN into `backend/.env` as `SENTRY_DSN`, replacing `localhost:8036` with
  `glitchtip-web:8000` (the address the containers reach it at), and run
  `make up WITH=glitchtip` again.

Nothing leaves the machine: Grafana, Loki and Alloy have their usage reporting
turned off.

## Versions

Images are pinned. GlitchTip stays on 5.2.1: 6.x moved to its own database
driver, which fails on Postgres 18 while reading the system catalog.

## Files

```
compose.yaml          the stand; profiles prometheus, loki, grafana, glitchtip
compose.mail.yaml     Mailpit and the worker pointed at it (APP_ENV=local)
initdb/               roles and databases, on an empty volume only
prometheus/           scrape targets
loki/                 single-binary Loki on local disk
alloy/                log collection from this project's containers
grafana/              datasources and dashboards
rabbitmq/             management and prometheus plugins
```
