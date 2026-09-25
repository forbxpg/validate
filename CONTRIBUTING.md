# Contributing

> The code is still being moved in from the private prototype. The commands below are
> the ones the repository will keep once it lands; until then there is nothing to run.

## Layout

- `backend/` — a [uv](https://docs.astral.sh/uv/) workspace: `packages/*` holds one
  package per domain (users, journals, crossref, citations, articles, notifications),
  `apps/*` the processes that run them (API, worker, CLI for registry imports).
- `frontend/` — React and TypeScript, built with Vite.

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
make up        # PostgreSQL and Redis
make migrate   # apply migrations
make dev       # API on :8000 with reload
make worker    # TaskIQ worker for reference lists
```

Copy `.env.example` to `.env` first; it lists every variable with a value that works
for the stand. Registry imports (VAK PDF, White List) are CLI commands; their heavy
dependencies (PDF parsing, a headless browser) live in the CLI app only, so the API image
stays small.

## Checks

All of these must pass; CI runs the same.

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run basedpyright \
  && uv run lint-imports && uv run pytest
cd frontend && npm run lint && npx tsc -b && npm test && npm run build
```

Tests live in `tests/unit` and `tests/integration`; the integration ones need
PostgreSQL and Redis. `make test` starts the stand and runs the whole suite against a
database of its own, never the one `make dev` uses.

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
