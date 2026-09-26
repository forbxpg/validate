# validate

**Check a journal before you submit to it.** validate tells a graduate student whether a
journal is on Russia's VAK list or the “White List”, and for which specialities, then
builds the reference list: give it DOIs, get entries formatted to GOST R 7.0.100-2018
and a `.bib` file for LaTeX.

> **Status: moving in.** The service runs today from a private prototype. Its code is
> being moved here into a uv workspace, one domain at a time; the pieces below are
> already here.

- Backend: Python, FastAPI, PostgreSQL, Redis, TaskIQ. Frontend: React and TypeScript.
  The interface is in Russian.
- Security reports: see [SECURITY.md](SECURITY.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

## What is here

| Part | What it does |
|---|---|
| [`backend/packages/core`](backend/packages/core/README.md) | settings, database, Redis, rate limits, logs, the audit log |
| [`backend/packages/web`](backend/packages/web/README.md) | shared HTTP layer: errors, access markers, session cookies |
| [`backend/packages/auth`](backend/packages/auth/README.md) | accounts, email and password login, sessions, roles, administration |
| [`backend/packages/crossref`](backend/packages/crossref/README.md) | `vld-crossref`: an async typed client of the Crossref REST API and its command line |
| [`backend/packages/vak`](backend/packages/vak/README.md) | `vld-vak`: the VAK list PDF as typed data, every doubt reported |
| [`backend/apps/api`](backend/apps/api/README.md) | the HTTP API |
| [`backend/apps/worker`](backend/apps/worker/README.md) | relays the outbox to RabbitMQ and sends the letters |
| [`backend/apps/migrator`](backend/apps/migrator/README.md) | `vld-migrate`: database migrations with a lock, checks and a backup |
| [`infrastructure`](infrastructure/README.md) | the local stand in Docker (`make dev`), with optional Prometheus, Loki, Grafana and GlitchTip |

Set up once, then run the whole stand in Docker (details in
[CONTRIBUTING.md](CONTRIBUTING.md) and [infrastructure/README.md](infrastructure/README.md)):

```bash
cd backend && uv sync --all-packages && cd ..
cp backend/.env.example backend/.env
make dev
```

Licensed under [AGPL-3.0](LICENSE). If you run a modified copy as a public service,
the licence requires you to offer its source to your users.
