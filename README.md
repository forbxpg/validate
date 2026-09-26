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
| `backend/packages/core` | settings, database, Redis, rate limits, logs, the audit log |
| `backend/packages/web` | shared HTTP layer: errors, access markers, session cookies |
| `backend/packages/auth` | accounts, email and password login, sessions, roles, administration |
| `backend/packages/crossref` | `vld-crossref`: an async typed client of the Crossref REST API and its command line |
| `backend/apps/api` | the HTTP API |
| `backend/apps/worker` | relays the outbox to RabbitMQ and sends the letters |
| `backend/apps/migrator` | `vld-migrate`: database migrations with a lock, checks and a backup |

Set up once:

```bash
cd backend
uv sync --all-packages
```

## Crossref from the terminal

`vld-crossref` asks [Crossref](https://api.crossref.org) for works and journals. In
this workspace `uv sync --all-packages` installs it; elsewhere install the package
with its extra: `pip install 'vld-crossref[cli]'` (or `[all]`).

Tell Crossref who you are, once, in `backend/.env` or the environment:

```bash
CROSSREF_MAILTO=you@example.org      # the polite pool: 10 requests a second, 3 at a time
# CROSSREF_PLUS_TOKEN=...            # Crossref Plus, if you have it
# CROSSREF_OUTPUT_DIR=crossref-output  # where --save-json writes
```

Without an address the command uses the public pool (5 requests a second, one at a
time) and says so. `.env` is read only from the folder you run the command in.

### Works

```bash
uv run vld-crossref works get 10.1103/PhysRevLett.1.1          # any form: doi:…, https://doi.org/…
uv run vld-crossref works exists 10.1103/PhysRevLett.1.1       # exit code 0 or 1
uv run vld-crossref works agency 10.1103/PhysRevLett.1.1

uv run vld-crossref works search graphene --author geim --type journal-article --from 2010
uv run vld-crossref works search --title "random walk" --sort published --order desc --rows 50
uv run vld-crossref works search --filter until-online-pub-date=2024 --facet type-name:10
uv run vld-crossref works search --journal 0031-9007 --from 2024      # works of one journal

uv run vld-crossref works iterate --prefix 10.1103 --max 500         # the cursor walk
uv run vld-crossref works sample --size 5 --type book-chapter
uv run vld-crossref works filters                                   # every --filter name
```

- Free text goes first; 21 field queries are flags: `--author`, `--title`,
  `--bibliographic`, `--affiliation`, `--editor`, `--container-title`,
  `--funder-name`, `--publisher-name`, and the rest (`--help` lists them).
- Common filters have their own flags: `--type`, `--from`, `--until` (dates as
  `2024`, `2024-05` or `2024-05-17`), `--issn`, `--orcid`, `--prefix`, `--member`,
  `--has-orcid`, `--has-abstract`. Any of the 90 Crossref filters works through
  `--filter name=value`; repeating a filter ORs its values.
- `search` returns one page (`--rows` 1..1000, `--offset`; together at most 10,000).
  `iterate` walks with the cursor: 100 records unless `--max N` or `--all`.

### Journals

```bash
uv run vld-crossref journals get 0031-9007
uv run vld-crossref journals exists 00319007
uv run vld-crossref journals search "physical review" --rows 20
uv run vld-crossref journals iterate --all --save-json            # all ~171,000 journals
```

### Output and saving

- In a terminal: a card for one record, a table for lists, and a summary line
  (`20 of 1 234 567 · pool: polite`).
- Piped or with `--json`: JSON for `get` and `search`, JSON Lines (one record per
  line) for `iterate` and `sample`, with Crossref's field names. Messages and logs go
  to stderr, so `| jq` always gets data:

  ```bash
  uv run vld-crossref works search graphene --rows 5 | jq '.items[].DOI'
  ```

- `--save-json` also writes the result into `CROSSREF_OUTPUT_DIR` or
  `./crossref-output/` (ignored by git): `.json`, or `.jsonl` for `iterate`,
  written as records arrive, so Ctrl-C keeps what was received. `--out-dir DIR`
  changes the folder, `--out FILE` names the file.
- `-v` shows debug logs and tracebacks.

| Exit code | Meaning |
|---|---|
| 0 | done |
| 1 | not found, or `exists` says no |
| 2 | the query is wrong (checked before any request) |
| 3 | Crossref refused or failed (rate limit, block, outage) |
| 130 | interrupted |

## Crossref in code

```python
from vld.crossref import (
    CrossrefClient,
    LocalThrottle,
    PartialDate,
    RateLimits,
    WorksFilter,
    WorksQuery,
)

async with CrossrefClient(
    mailto="you@example.org",
    throttle=LocalThrottle(RateLimits.POLITE),
    app="validate/1.0",
) as client:
    work = await client.works.get("10.1103/PhysRevLett.1.1")
    page = await client.works.search(
        WorksQuery(text="graphene", filter=WorksFilter(from_pub_date=PartialDate(2024))),
        rows=20,
    )
    async for journal in client.journals.iterate(max_items=None):
        ...
```

Limits, retries, errors, tolerant models and the tests are described in
[backend/packages/crossref/README.md](backend/packages/crossref/README.md).

Licensed under [AGPL-3.0](LICENSE). If you run a modified copy as a public service,
the licence requires you to offer its source to your users.
