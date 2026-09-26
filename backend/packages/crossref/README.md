# vld-crossref

Asynchronous, typed client of the [Crossref REST API](https://api.crossref.org):
works and journals, with every parameter of their routes.

A standalone library: it imports `httpx`, `pydantic`, `tenacity`, `structlog`
and the standard library, never another `vld` package. The import-linter
contract "crossref is a standalone library" in the root `pyproject.toml` holds
that.

## Usage

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
    mailto="support@example.org",  # None: the public pool, on purpose
    throttle=LocalThrottle(RateLimits.POLITE),
    app="validate/1.0",  # product/version, sent in User-Agent
) as client:
    work = await client.works.get("https://doi.org/10.1103/PhysRevLett.1.1")
    known = await client.works.exists("10.1103/physrevlett.1.1")
    page = await client.works.search(
        WorksQuery(
            text="graphene", filter=WorksFilter(from_pub_date=PartialDate(2024))
        ),
        rows=20,
    )
    async for work in client.works.iterate(
        WorksQuery(filter=WorksFilter(prefix="10.1103")),
        max_items=5000,  # None walks everything, on purpose
    ):
        ...
    journal = await client.journals.get("0031 9007")
    async for journal in client.journals.iterate(max_items=None):
        ...
    recent = await client.journals.works("0031-9007").search(
        WorksQuery(filter=WorksFilter(from_pub_date=PartialDate(2024))),
        rows=50,
    )
```

`mailto`, `throttle` and `app` have no defaults: the call site shows which pool
the client asks for and how it keeps to its limits. With `http=None` the client
opens and closes its own `httpx.AsyncClient`; a passed one is left open, which
is also how an HTTP cache is plugged in from outside. The library caches
nothing.

## Limits

Crossref counts requests per identity, not per process:

| Pool | Requests per second | Concurrent | Identity |
|---|---|---|---|
| public | 5 | 1 | none (`mailto=None`) |
| polite | 10 | 3 | `mailto` |
| plus | 150 | no limit | `plus_token` |

`LocalThrottle` keeps one process inside the limits and follows the
`x-rate-limit-limit`, `x-rate-limit-interval` and `x-concurrency-limit` headers
of every answer. Several processes with one identity need one shared `Throttle`
(the protocol has `slot()` and `observe(limits)`); that one belongs to the
application.

## Retries and errors

429, 5xx, timeouts and broken connections are tried again by `RetryPolicy`
(5 attempts; the wait is `Retry-After` when Crossref sends it, otherwise
exponential backoff from 1 s with full jitter; never over 30 s). 400, 403 and 404 are never retried. Each attempt takes a new throttle
slot.

| Error (all derive from `CrossrefError`) | When |
|---|---|
| `CrossrefQueryError` | refused before any request: a bad identifier, bounds, a query that contradicts itself |
| `CrossrefBadRequestError` | Crossref answered 400; `problems` holds its `ValidationProblem`s |
| `CrossrefRateLimitedError` | still 429 after the last attempt; `retry_after` |
| `CrossrefBlockedError` | 403: blocked by hand, retrying is useless |
| `CrossrefUnavailableError` | 5xx, timeout or connection failure after the last attempt; `status` |
| `CrossrefSchemaError` | the envelope is not what Crossref promises |
| `CrossrefCursorExpiredError` | a walk paused longer than the five-minute life of a cursor |

Errors and logs carry the URL without `mailto`; headers are never logged.

## Reading

- Not found is not an error: `get` returns `None` and `exists` returns `False`.
- `search(rows=, offset=)` is one page for numbered screens; `offset + rows`
  stays within 10,000, as Crossref allows. `iterate(max_items=)` walks with
  the cursor through any number of records. `sample(size=)` gives up to 100
  random records.
- A malformed field of a record becomes empty and logs
  `crossref_field_degraded` with the record id; the record stays. A record
  without a valid identity (DOI or ISSN) is left out of a page with
  `crossref_item_dropped`.
- `PartialDate(year, month, day)` keeps the precision Crossref has and never
  invents a month or a day; `earliest()` and `latest()` give the bounds.
- `normalize_doi`, `normalize_issn` accept the common forms (links, `doi:`,
  spaces, a missing hyphen) and are public, so the application uses the same
  rules for its own input.

## Command line

Installed with `vld-crossref[cli]` (or `vld-crossref[all]`); in this workspace
`uv sync --all-packages` already brings it.

```bash
vld-crossref works get 10.1103/PhysRevLett.1.1
vld-crossref works search graphene --author geim --type journal-article --from 2010
vld-crossref works search --filter until-online-pub-date=2024 --facet type-name:10
vld-crossref works iterate --prefix 10.1103 --max 500 --save-json
vld-crossref works sample --size 5 --journal 0031-9007
vld-crossref works filters                      # every filter --filter takes
vld-crossref journals get 0031-9007
vld-crossref journals iterate --all --save-json
```

- In a terminal the output is a card or a table with a summary line; piped or
  with `--json` it is JSON (`get`, `search`) or JSON Lines (`iterate`,
  `sample`). Logs go to stderr, so `| jq` always gets data.
- `--save-json` also writes the result: `.json`, or `.jsonl` for `iterate`,
  appended as records arrive, so Ctrl-C keeps what was received. The folder is
  `--out-dir`, else `CROSSREF_OUTPUT_DIR`, else `./crossref-output/`; `--out
  FILE` names the file.
- `CROSSREF_MAILTO` (or `--mailto`) asks for the polite pool; without it the
  public pool is used and the command says so. `CROSSREF_PLUS_TOKEN` selects
  Plus. Both are read from the environment or `.env` of the current folder.
- `iterate` takes 100 records unless `--max N` or `--all`.
- Exit codes: 0 done, 1 not found (or `exists` says no), 2 a bad query,
  3 Crossref refused or failed, 130 interrupted.

## Layout

```
src/vld/crossref/
├── _client.py      CrossrefClient
├── transport/      the only code that talks HTTP: identity, envelope, retries
├── throttle/       Throttle protocol, RateLimits, LocalThrottle
├── errors/
├── pagination/     Page, facets, the cursor walk
├── ids/            identifier normalizers
├── models/         tolerant model machinery, dates, shared field types, query base
├── works/          WorksResource, WorkList, query/ (WorksQuery, WorksFilter), model/ (Work)
├── journals/       JournalsResource, JournalsQuery, Journal
└── cli/            the vld-crossref command, with the cli extra
```

## Tests

```bash
uv run pytest packages/crossref
CROSSREF_LIVE_MAILTO=you@example.org uv run pytest -m crossref_live packages/crossref
```

The unit tests answer through `httpx.MockTransport` in virtual time
(`tests/support/crossref_support.py`). The live tests call the real Crossref;
they are left out of the default run and of CI (`CROSSREF_LIVE_MAILTO=public`
uses no address).

`tests/fixtures/` holds recorded Crossref answers; the `*_handmade` ones are
broken copies the recorder makes on purpose. To record them again:

```bash
uv run python packages/crossref/scripts/record_fixtures.py --mailto you@example.org
```
