# Contributing

## Layout

- `backend/` — a [uv](https://docs.astral.sh/uv/) workspace. `packages/*` are
  libraries: `core` (settings, database, Redis, logs, audit), `web` (the shared HTTP
  layer), the domains (`auth` so far) and `crossref`, a standalone client of the
  Crossref API. `apps/*` are the processes: `api`, `worker` (outbox relay and
  letters), `migrator` (`vld-migrate`).
- `frontend/` — React and TypeScript, built with Vite.
- `infrastructure/` — the local stand in Docker, run through the root `Makefile`.

Domains see each other only through their `application/contracts`, and `domain` and
`application` never import infrastructure. `import-linter` checks both; a violation
fails CI.

## Set up

You need uv, Node 20+ and Docker.

```bash
cd backend && uv sync --all-packages
cd frontend && npm ci
```

## Local stand

```bash
cp backend/.env.example backend/.env   # once
make dev                               # the whole stand in Docker, code synced
make dev WITH=obs                      # plus Prometheus, Loki, Grafana, GlitchTip
make help                              # every target
```

`make dev` builds the images, runs the migrator once, starts the API on
http://localhost:8010 and the worker, and syncs code changes into them. With
`APP_ENV=local` letters land in Mailpit (http://localhost:8035). Ports, the
optional services and how to connect GlitchTip: [infrastructure/README.md](infrastructure/README.md).
`make api-host` runs the API on the host instead, for a debugger.

## Checks

All of these must pass; CI runs the same.

```bash
make check              # ruff, basedpyright, import contracts, unit tests
make test-integration   # against the running stand
cd frontend && npm run lint && npx tsc -b && npm test && npm run build
```

Tests live in `tests/unit` and `tests/integration`; the integration ones need the
stand's PostgreSQL and Redis. Their fixtures create and drop `test_` databases of their
own and Redis index 15 (`make test-integration` sets both), never what `make dev` uses.

Conventions: English in code, docstrings and commits; Russian in the interface only.
Google-style docstrings on every module, class and function, `from __future__ import
annotations` in every module, Python 3.13. Only names in `__all__` are public.

## Registry data

The VAK list and the White List change several times a year. A data fix is a change to
the import, not to the database: update the parser or the source file, add a test with
the journal that was wrong, and re-run the import.

## Commits and pull requests

Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `build:`, `ci:`, `chore:`; `!` for
breaking changes). The PR title becomes the squashed commit.

By contributing you agree that your contribution is licensed under [AGPL-3.0](LICENSE).

## Security

Found a vulnerability? Do not open an issue: follow [SECURITY.md](SECURITY.md).
