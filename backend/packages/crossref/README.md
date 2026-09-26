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

`vld-crossref` asks Crossref from a terminal. It comes with the `cli` extra:

```bash
pip install 'vld-crossref[cli]'      # or [all]; typer and python-dotenv
uv sync --all-packages               # in this workspace it is already installed
uv run vld-crossref --help
```

Without the extra the command exists but only says how to install it (exit 2).

### Who is asking

| Variable | Flag | Meaning |
|---|---|---|
| `CROSSREF_MAILTO` | `--mailto` | Address for the polite pool (10 requests a second, 3 at a time). Without it: the public pool (5 a second, 1 at a time), and a warning on stderr |
| `CROSSREF_PLUS_TOKEN` | — | Crossref Plus token: the Plus pool |
| `CROSSREF_OUTPUT_DIR` | `--out-dir` | Folder of `--save-json`; default `./crossref-output/` |

A flag wins over the environment, the environment over `.env`. Only `.env` of the
folder you run the command in is read, never of its parents.

### Commands

| Command | Does |
|---|---|
| `works get DOI` | one work as a card; the DOI in any form (`10.…`, `doi:10.…`, `https://doi.org/10.…`) |
| `works exists DOI` | `yes` / `no`, exit 0 / 1 |
| `works agency DOI` | the registration agency of the DOI |
| `works search [TEXT] …` | one page: `--rows` (20; 1..1000), `--offset` (offset + rows ≤ 10,000) |
| `works iterate [TEXT] …` | the cursor walk: 100 records unless `--max N` or `--all`; `--page-size` (1000) |
| `works sample [TEXT] …` | random works: `--size` (10; 1..100) |
| `works filters` | every filter `--filter` takes: name, kind of value, whether it repeats |
| `journals get ISSN` | one journal as a card; `0031-9007`, `0031 9007` or `00319007` |
| `journals exists ISSN` | `yes` / `no`, exit 0 / 1 |
| `journals search [TEXT]` | one page: `--rows`, `--offset` |
| `journals iterate [TEXT]` | the cursor walk over journals: 100 unless `--max N` or `--all` |

`search`, `iterate` and `sample` of works take the same query options:

- **Free text** — the first argument: `works search "graphene oxide"`.
- **Field queries** — search in one field: `--affiliation`, `--author`,
  `--bibliographic`, `--chair`, `--container-title`, `--contributor`, `--degree`,
  `--description`, `--editor`, `--event-acronym`, `--event-location`,
  `--event-name`, `--event-sponsor`, `--event-theme`, `--funder-name`,
  `--publisher-location`, `--publisher-name`, `--standards-body-acronym`,
  `--standards-body-name`, `--title`, `--translator`.
- **Common filters** — `--type` (repeat to OR; `works filters` lists the types),
  `--from` / `--until` (publication date: `2024`, `2024-05` or `2024-05-17`),
  `--issn`, `--orcid`, `--prefix`, `--member` (each repeatable),
  `--has-orcid` / `--no-orcid`, `--has-abstract` / `--no-abstract`.
- **Any other filter** — `--filter name=value` with the Crossref name, repeatable:
  `--filter from-online-pub-date=2024-05 --filter has-funder=true`. Dates as
  above; deposit-side times need a zone: `--filter from-index-date=2024-05-17T10:00:00Z`;
  yes/no filters take `true`/`false`. A repeated many-valued filter ORs; a
  single-valued one refuses a second value.
- **One journal** — `--journal ISSN` sends the query to `/journals/{issn}/works`.
- **Order and facets** (`search`, `iterate`) — `--sort` (`created`, `deposited`,
  `indexed`, `is-referenced-by-count`, `issued`, `published`, `published-online`,
  `published-print`, `references-count`, `relevance`, `score`, `updated`),
  `--order asc|desc` (needs `--sort`), `--facet name[:count]` (repeatable:
  `affiliation`, `archive`, `assertion`, `assertion-group`, `category-name`,
  `container-title`, `funder-doi`, `funder-name`, `issn`, `journal-issue`,
  `journal-volume`, `license`, `link-application`, `orcid`, `published`,
  `publisher-name`, `relation-type`, `ror-id`, `source`, `type-name`,
  `update-type`).

Every option is checked before any request: a typo in a filter, a bad date or
`--order` without `--sort` exits 2 with a message.

### Examples

```bash
vld-crossref works get https://doi.org/10.1103/PhysRevLett.1.1
vld-crossref works search graphene --author geim --type journal-article --from 2010
vld-crossref works search --title "random walk" --sort published --order desc --rows 50
vld-crossref works search --filter until-online-pub-date=2024 --facet type-name:10 --rows 1
vld-crossref works search --journal 0031-9007 --from 2024 --has-abstract
vld-crossref works iterate --prefix 10.1103 --max 500 --save-json
vld-crossref works sample --size 5 --type book-chapter
vld-crossref journals search "physical review"
vld-crossref journals iterate --all --save-json        # every journal, about 171,000
```

### Output

In a terminal: a card for `get`, a table for lists with a summary line such as
`20 of 1 234 567 · pool: polite`, and one table per facet.

Piped, redirected or with `--json`: data only, with Crossref's field names
(`DOI`, `container-title`, …):

| Command | Format |
|---|---|
| `get`, `agency`, `exists` | one JSON object |
| `search` | one JSON object: `total_results`, `offset`, `rows`, `facets`, `items` |
| `iterate`, `sample` | JSON Lines, one record per line, printed as they arrive |

Messages, warnings and logs go to stderr, so a pipe always gets clean data:

```bash
vld-crossref works search graphene --rows 5 | jq '.items[].DOI'
vld-crossref works iterate --issn 0031-9007 --max 1000 | jq -r '.DOI'
vld-crossref works exists 10.1103/PhysRevLett.1.1 && echo registered
```

`-v` adds debug logs (every request) and tracebacks on stderr.

### Saving

`--save-json` writes the same data into a file and keeps the terminal output:

- `.json` for `get`, `exists`, `agency`, `search`, `sample`; `.jsonl` for
  `iterate`, written and flushed record by record, so Ctrl-C keeps everything
  received so far.
- Folder: `--out-dir`, else `CROSSREF_OUTPUT_DIR`, else `./crossref-output/`
  (created when missing; `crossref-output/` is ignored by git).
- Name: `<resource>-<command>-<what>-<time>.json`, for example
  `works-get-10.1103_physrevlett.1.1-20260926T141500.json`; for queries `<what>`
  is the first 8 characters of the query fingerprint.
- `--out FILE` gives the file itself and implies saving; an existing file is
  replaced.
- The path is printed to stderr.

JSON Lines read directly: `pandas.read_json(path, lines=True)`,
`duckdb.read_json_auto(path)`, `jq`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | done |
| 1 | not found, or `exists` says no |
| 2 | the query is wrong, refused before any request or by Crossref (400) |
| 3 | Crossref rate limit after the retries, a block (403) or an outage |
| 130 | interrupted (Ctrl-C); for a saved walk, how many records were written |

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
