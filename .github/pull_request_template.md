## What and why

## Checklist

- [ ] The title follows Conventional Commits (`feat: …`, `fix: …`).
- [ ] Tests cover the change; a registry data fix adds a test with the journal that was wrong.
- [ ] Backend checks pass: `uv run ruff check . && uv run basedpyright && uv run lint-imports && uv run pytest`.
- [ ] Frontend checks pass if it changed: `npm run lint && npx tsc -b && npm test && npm run build`.
- [ ] Not a security report: those go through [SECURITY.md](../SECURITY.md).
