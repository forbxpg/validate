# vld-crossref

Client of the Crossref REST API.

## What's inside

```
core/    errors of the API and the retry policy
```

- `CrossrefAPIError` and its cases carry an HTTP status, a message for the user
  and optional details; `to_dict()` gives the body of an error response.
- `retry(attempts, delay_seconds, errors)` calls an async function again after
  a rate limit, a timeout or a 5xx (`TRANSIENT_ERRORS`). The last error is
  raised as it is; a permanent one, such as "not found", is raised at once.

## Tests

```bash
uv run pytest packages/crossref
```
