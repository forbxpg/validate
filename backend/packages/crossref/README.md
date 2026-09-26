# vld-crossref

Asynchronous, typed client of the [Crossref REST API](https://api.crossref.org):
the client, limits, retries, errors, pages and cursors, identifiers and dates.

A standalone library: it imports `httpx`, `pydantic`, `tenacity`, `structlog`
and the standard library, never another `vld` package. The import-linter
contract "crossref is a standalone library" in the root `pyproject.toml` holds
that.

## Usage

```python
from vld.crossref import (
    CrossrefClient,
    LocalThrottle,
    RateLimits,
)

async with CrossrefClient(
    mailto="support@example.org",  # None: the public pool, on purpose
    throttle=LocalThrottle(RateLimits.POLITE),
    app="validate/1.0",  # product/version, sent in User-Agent
) as client:
    print(client.pool)  # the pool of the last answer: public, polite or plus
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

## Identifiers and dates

- `normalize_doi` and `normalize_issn` accept the common forms (links, `doi:`,
  spaces, a missing hyphen) and refuse the rest with `CrossrefQueryError`.
- `PartialDate(year, month, day)` keeps the precision Crossref has and never
  invents a month or a day; `earliest()` and `latest()` give the bounds.

## Layout

```
src/vld/crossref/
├── _client.py      CrossrefClient
├── transport/      the only code that talks HTTP: identity, envelope, retries
├── throttle/       Throttle protocol, RateLimits, LocalThrottle
├── errors/
├── pagination/     Page, facets, the cursor walk
├── ids/            identifier normalizers
└── models/         tolerant model machinery, dates
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