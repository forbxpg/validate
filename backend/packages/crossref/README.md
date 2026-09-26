# vld-crossref

Asynchronous, typed client of the [Crossref REST API](https://api.crossref.org)
for works and journals — every parameter of their routes — and `vld-crossref`,
a command line over it.

The library is standalone: it imports `httpx`, `pydantic`, `tenacity`,
`structlog` and the standard library, never another `vld` package. Two
import-linter contracts in the root `pyproject.toml` hold that and keep the
command line out of the core.

- [Install](#install)
- [Quick start](#quick-start)
- [Command line](#command-line)
- [Library](#library)
- [Limits, retries, errors](#limits-retries-errors)
- [Layout](#layout) · [Tests](#tests)

## Install

```bash
pip install vld-crossref              # the library
pip install 'vld-crossref[cli]'       # plus the vld-crossref command (typer, python-dotenv)
pip install 'vld-crossref[all]'       # everything; the same as [cli] today
```

In this workspace `uv sync --all-packages` installs both; run the command with
`uv run vld-crossref`. Installed without the extra, `vld-crossref` only says how
to install it (exit 2).

## Quick start

```bash
export CROSSREF_MAILTO=you@example.org          # the polite pool; optional

vld-crossref works get 10.1103/PhysRevLett.1.1
vld-crossref works search graphene --author geim --from 2010 --rows 5
vld-crossref journals get 0031-9007
```

```python
from vld.crossref import CrossrefClient, LocalThrottle, RateLimits, WorksQuery

async with CrossrefClient(
    mailto="you@example.org",
    throttle=LocalThrottle(RateLimits.POLITE),
    app="validate/1.0",
) as client:
    work = await client.works.get("10.1103/PhysRevLett.1.1")
    page = await client.works.search(WorksQuery(text="graphene"), rows=5)
```

## Command line

### Who is asking

| Variable | Flag | Meaning |
|---|---|---|
| `CROSSREF_MAILTO` | `--mailto` | Address for the polite pool. Without it the public pool is used, and the command says so on stderr |
| `CROSSREF_PLUS_TOKEN` | — | Crossref Plus token: the Plus pool |
| `CROSSREF_OUTPUT_DIR` | `--out-dir` | Folder for `--save-json`; default `./crossref-output/` |

A flag wins over the environment, the environment over `.env`. Only the `.env`
of the folder you run the command in is read, never one of its parents.

### Commands

| Command | Does |
|---|---|
| `works get DOI` | one work; the DOI in any form: `10.…`, `doi:10.…`, `https://doi.org/10.…` |
| `works exists DOI` | whether Crossref knows the DOI: prints `yes` / `no`, exits 0 / 1 |
| `works agency DOI` | the registration agency of the DOI |
| `works search [TEXT]` | one page of works: `--rows` (20, up to 1000), `--offset` (offset + rows ≤ 10,000) |
| `works iterate [TEXT]` | walks the works with the cursor: 100 unless `--max N` or `--all`; `--page-size` (1000) |
| `works sample [TEXT]` | random works: `--size` (10, up to 100) |
| `works filters` | every filter `--filter` takes, with the kind of value and whether it repeats |
| `journals get ISSN` | one journal; `0031-9007`, `0031 9007` or `00319007` |
| `journals exists ISSN` | whether Crossref knows the journal: `yes` / `no`, exit 0 / 1 |
| `journals search [TEXT]` | one page of journals: `--rows`, `--offset` |
| `journals iterate [TEXT]` | walks all journals: 100 unless `--max N` or `--all` |

Every command also takes `--mailto`, `--json`, `--save-json`, `--out-dir`,
`--out FILE` and `-v`; `--help` on any command lists its options.

### Query options of works

`works search`, `works iterate` and `works sample` take the same query.

**Free text** is the first argument: `works search "graphene oxide"`.

**Field queries** search in one field of the record:

| | | |
|---|---|---|
| `--affiliation` | `--description` | `--funder-name` |
| `--author` | `--editor` | `--publisher-location` |
| `--bibliographic` | `--event-acronym` | `--publisher-name` |
| `--chair` | `--event-location` | `--standards-body-acronym` |
| `--container-title` | `--event-name` | `--standards-body-name` |
| `--contributor` | `--event-sponsor` | `--title` |
| `--degree` | `--event-theme` | `--translator` |

**Common filters** have their own options:

| Option | Filter | Value |
|---|---|---|
| `--type` | `type` | a work type, such as `journal-article`; repeat to OR |
| `--from`, `--until` | `from-pub-date`, `until-pub-date` | `2024`, `2024-05` or `2024-05-17` |
| `--issn` | `issn` | ISSN of the journal; repeat to OR |
| `--orcid` | `orcid` | ORCID iD of a contributor; repeat to OR |
| `--prefix` | `prefix` | DOI prefix, such as `10.1103`; repeat to OR |
| `--member` | `member` | Crossref member id; repeat to OR |
| `--has-orcid` / `--no-orcid` | `has-orcid` | only works with (without) an ORCID iD |
| `--has-abstract` / `--no-abstract` | `has-abstract` | only works with (without) an abstract |

**Any of the 90 filters** goes through `--filter name=value` with the Crossref
name; `works filters` lists them. Repeating a filter that takes many values ORs
them; a filter with one value refuses a second one.

```bash
--filter from-online-pub-date=2024-05              # dates: 2024, 2024-05, 2024-05-17
--filter from-index-date=2024-05-17T10:00:00Z      # deposit-side times need a zone
--filter has-funder=true                           # yes/no filters: true or false
--filter issn=0031-9007 --filter issn=1079-7114    # OR
```

**One journal:** `--journal ISSN` asks `/journals/{issn}/works` instead of `/works`.

**Sort and facets** (`search`, `iterate`):

- `--sort FIELD` with `--order asc|desc`: `created`, `deposited`, `indexed`,
  `is-referenced-by-count`, `issued`, `published`, `published-online`,
  `published-print`, `references-count`, `relevance`, `score`, `updated`.
- `--facet NAME[:COUNT]`, repeatable: `affiliation`, `archive`, `assertion`,
  `assertion-group`, `category-name`, `container-title`, `funder-doi`,
  `funder-name`, `issn`, `journal-issue`, `journal-volume`, `license`,
  `link-application`, `orcid`, `published`, `publisher-name`, `relation-type`,
  `ror-id`, `source`, `type-name`, `update-type`.

Everything is checked before a request is sent: a typo in a filter, a bad date or
`--order` without `--sort` exits 2 with a message saying what to fix.

### Examples

```bash
vld-crossref works get https://doi.org/10.1103/PhysRevLett.1.1
vld-crossref works search graphene --author geim --type journal-article --from 2010
vld-crossref works search --title "random walk" --sort published --order desc --rows 50
vld-crossref works search --filter has-funder=true --facet type-name:10 --rows 1
vld-crossref works search --journal 0031-9007 --from 2024 --has-abstract
vld-crossref works iterate --prefix 10.1103 --max 500 --save-json
vld-crossref works sample --size 5 --type book-chapter
vld-crossref journals search "physical review"
vld-crossref journals iterate --all --save-json          # every journal, about 171,000
```

### Output

In a terminal you get a card for one record, a table for a list and a summary
line such as `20 of 1 234 567 · pool: polite`; facets come as their own tables.

Piped, redirected or with `--json`, stdout carries data only, with Crossref's
field names (`DOI`, `container-title`, …):

| Command | Output |
|---|---|
| `get`, `exists`, `agency` | one JSON object |
| `search` | one JSON object: `total_results`, `offset`, `rows`, `facets`, `items` |
| `iterate`, `sample` | JSON Lines: one record per line, printed as they arrive |

Messages, warnings and logs go to stderr, so a pipe always gets clean data. `-v`
adds a debug line per request and full tracebacks.

```bash
vld-crossref works search graphene --rows 5 | jq '.items[].DOI'
vld-crossref works iterate --issn 0031-9007 --max 1000 | jq -r '.DOI'
vld-crossref works exists 10.1103/PhysRevLett.1.1 && echo registered
```

### Saving

`--save-json` writes the same data into a file; the terminal output stays.

- `get`, `exists`, `agency`, `search` and `sample` write `.json`; `iterate` writes
  `.jsonl`, record by record, so Ctrl-C keeps everything received so far.
- The folder is `--out-dir`, else `CROSSREF_OUTPUT_DIR`, else `./crossref-output/`
  (created when missing, ignored by git).
- The name is `<resource>-<command>-<what>-<time>`, for example
  `works-get-10.1103_physrevlett.1.1-20260926T141500.json`; for a query `<what>` is
  the start of its fingerprint.
- `--out FILE` names the file itself and implies saving; an existing file is
  replaced.
- The path of the file is printed on stderr.

JSON Lines open directly in `pandas.read_json(path, lines=True)`,
`duckdb.read_json_auto(path)` and `jq`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | done |
| 1 | not found, or `exists` answered no |
| 2 | the query is wrong: refused before the request or by Crossref (400) |
| 3 | Crossref failed: rate limit after the retries, a block (403), an outage |
| 130 | interrupted; a saved walk reports how many records it wrote |

## Library

### The client

```python
from vld.crossref import CrossrefClient, LocalThrottle, RateLimits

async with CrossrefClient(
    mailto="you@example.org",  # None asks for the public pool, on purpose
    throttle=LocalThrottle(RateLimits.POLITE),
    app="validate/1.0",  # product/version, sent in User-Agent
    plus_token=None,  # SecretStr for Crossref Plus
    timeout=10.0,  # seconds per request
) as client:
    ...
```

`mailto`, `throttle` and `app` have no defaults, so the call site shows which
pool the client asks for and how it keeps to its limits. `client.pool` names
the pool of the last answer. With `http=None` the client opens and closes its
own `httpx.AsyncClient`; a client passed in is left open, which is also how an
HTTP cache is plugged in. The library caches nothing.

### Works and journals

| Call | Returns |
|---|---|
| `client.works.get(doi)` | `Work`, or `None` if Crossref does not know the DOI |
| `client.works.exists(doi)` | `bool`, asked with `HEAD` |
| `client.works.agency(doi)` | `WorkAgency`, or `None` |
| `client.works.search(query, rows=20, offset=0)` | `Page[Work]` |
| `client.works.iterate(query, max_items=N, page_size=1000)` | async iterator of `Work`; `max_items=None` walks everything |
| `client.works.sample(query, size=N)` | `tuple[Work, ...]`, up to 100 |
| `client.journals.get(issn)`, `.exists(issn)` | `Journal` or `None`; `bool` |
| `client.journals.search(query, rows=, offset=)`, `.iterate(query, max_items=)` | `Page[Journal]`; async iterator of `Journal` |
| `client.journals.works(issn)` | the same `search` / `iterate` / `sample` over `/journals/{issn}/works` |

DOIs and ISSNs are accepted in any common form; `normalize_doi`,
`normalize_issn` and friends in `vld.crossref.ids` are public, so an
application can use the same rules for its own input.

### Queries

A query is a frozen value, rendered into parameters by the library:

```python
from vld.crossref import (
    Order,
    PartialDate,
    WorkFacet,
    WorksFilter,
    WorksQuery,
    WorksSort,
    WorkType,
)

query = WorksQuery(
    text="graphene",
    author="Geim",  # any of the 21 field queries
    filter=WorksFilter(
        type=[WorkType.JOURNAL_ARTICLE],  # one value or a list; a list ORs
        from_pub_date=PartialDate(2010),
        has_orcid=True,
    ),
    sort=WorksSort.PUBLISHED,
    order=Order.DESC,
    facets={WorkFacet.TYPE_NAME: 10},
)
query.params()  # the query string Crossref gets
query.fingerprint()  # a stable key, for a cache or a file name
```

`WorksFilter` holds all 90 filters Crossref accepts, typed. Mistakes — an
unknown field, a bad ISSN, `from` after `until`, `order` without `sort` —
raise `CrossrefQueryError` before any request. `JournalsQuery(text=...)` is the
whole query of `/journals`: that route takes nothing else.

### Results

- `Page[T]`: `items`, `total_results`, `items_per_page`, `offset`, `facets`.
- `Work` has every field Crossref sends, under Python names, plus `main_title`,
  `journal_title`, `issn_print`, `issn_electronic`, `publication_date`, `year`.
- `Journal` has `issn_print`, `issn_electronic`, `issns`, `total_dois`, counts,
  coverage and flags.
- Dates are `PartialDate(year, month, day)`: the precision Crossref has, never an
  invented month or day; `earliest()` and `latest()` give the bounds.
- Models are tolerant: a malformed field becomes empty and logs
  `crossref_field_degraded` with the record id; the record stays. A record
  without a valid identity (DOI, or any valid ISSN of a journal) is left out of a
  page and logged as `crossref_item_dropped`.

## Limits, retries, errors

Crossref counts requests per identity, not per process:

| Pool | Requests per second | At a time | Identity |
|---|---|---|---|
| public | 5 | 1 | none (`mailto=None`) |
| polite | 10 | 3 | `mailto` |
| plus | 150 | no limit | `plus_token` |

`LocalThrottle` keeps one process inside the limits and follows the
`x-rate-limit-limit`, `x-rate-limit-interval` and `x-concurrency-limit` headers
of every answer. Several processes with one identity need one shared `Throttle`
(the protocol is `slot()` and `observe(limits)`); that one belongs to the
application.

429, 5xx, timeouts and broken connections are tried again by `RetryPolicy`: 5
attempts, the wait is `Retry-After` when Crossref sends it, otherwise
exponential backoff from 1 s with full jitter, never over 30 s. 400, 403 and 404
are never retried. Each attempt takes a new throttle slot.

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
└── cli/            the vld-crossref command (the cli extra)
```

## Tests

```bash
uv run pytest packages/crossref
CROSSREF_LIVE_MAILTO=you@example.org uv run pytest -m crossref_live packages/crossref
```

The unit tests answer through `httpx.MockTransport` in virtual time
(`tests/support/crossref_support.py`); the command-line tests run the real
commands through `typer.testing.CliRunner` over the same fake Crossref. The live
tests call the real Crossref; they are left out of the default run and of CI
(`CROSSREF_LIVE_MAILTO=public` uses no address).

`tests/fixtures/` holds recorded Crossref answers; the `*_handmade` ones are
broken copies the recorder makes on purpose. To record them again:

```bash
uv run python packages/crossref/scripts/record_fixtures.py --mailto you@example.org
```
