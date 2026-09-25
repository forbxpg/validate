# vld-web

<hr>

Shared HTTP layer. Everything that is related to FastAPI, but does not belong to any domain:
who can call the route, how the error looks, how the domain is connected to the application,
how the rate limit is applied and how the list page looks.


<hr>

## What's inside

```
access/        access markers, session cookies, Origin check, identity
errors/        single error form, error code registries, handlers, X-Request-Id
mounting/      DomainDescriptor and mount(): connecting a domain with one object
throttling/    rate limits by client address on top of core.ratelimit
pagination/    HTTP page types: FeedPage (cursor) and TablePage (limit/offset)
```

<hr>

### `access/` — who can call the route

Each route declares exactly one marker in `dependencies=[...]`:

| Marker | Who can call the route |
|---|---|
| `public()` | everyone, without a token |
| `authenticated()` | any authenticated user |
| `roles(Role.STUDENT, ...)` | any user with one of the roles |
| `staff(Role.MODERATOR, ...)` | any user with one of the roles or with the admin flag |
| `admin()` | only the admin, the role is not important |
| `self_authenticated()` | a route that checks its own secret |

<b>Marker</b> — is a check. 

```mermaid
flowchart TD
    A[Client] -->|HTTP запрос| B[FastAPI Route]
    B -->|Getting token from cookie <br>validate_access, then from header <br>Authorization: Bearer| C[IdentityProvider]
    C -->|Sets identity| D[request.state]
    D -->|Identity(user_id, role, is_admin)| E[current_identity <br>or<br> optional_identity]
```
* Token is first taken from cookie `validate_access`, then from header `Authorization: Bearer`.
* Identity (`Identity`) is set in `request.state`, from where it is extracted by dependent components through `current_identity` or `optional_identity` for public routes.

<hr>

### `errors/` — error form

Any error from any domain looks the same (`ErrorResponse`):

```json
{
  "error": "auth.invalid_credentials", 
  "message": "Invalid email or password.",
  "details": null, 
  "request_id": "uuid4"
}
```

- `ErrorSpec(status, code, message)` — how one error looks outside.
- `ErrorRegistry(base, mapping, fallback_code)` — table «class of exception of the domain → ErrorSpec». Each domain declares its own (`api/_errors.py`);
  домена → ErrorSpec». Каждый домен объявляет свою (`api/_errors.py`);
- `CORE_ERRORS` (limits: 429 with `Retry-After`) and `ACCESS_ERRORS` (401, 403).
- `register_error_handlers` hangs handlers: domain registries, validation errors (422 with `details` by fields), `HTTPException` and everything unexpected (500 without details outward, with full traceback in the log).
- `RequestIdMiddleware` assigns `X-Request-Id` to the request (or takes the incoming one, if it is good), puts it in the log context and in the response.
  By this identifier, the request is searched in the logs and in GlitchTip.
- `_exc_info.py` does not allow the text of the database driver error to be logged, if there are values of the request parameters in it (personal data).

### `mounting/` — connecting a domain

A domain gives out one object `DomainDescriptor`:

```python
AUTH_DOMAIN = DomainDescriptor(
    router=router,  # APIRouter of the domain with all sub-routers
    errors=AUTH_ERRORS,  # error registry of the domain
    providers=(...),  # DI providers of the domain
    on_startup=startup,  # optional check at startup
)
```

`mount(app, *domains, prefix="/api/v1")`:


```mermaid
flowchart LR
    subgraph Domain 1
        A1[router]
        B1[errors]
        C1[providers]
    end
    subgraph Domain 2
        A2[router]
        B2[errors]
        C2[providers]
    end
    subgraph Domain N
        AN[router]
        BN[errors]
        CN[providers]
    end
    %% DomainDescriptors gather everything for each domain
    A1 & B1 & C1 --> D1[DomainDescriptor]
    A2 & B2 & C2 --> D2[DomainDescriptor]
    AN & BN & CN --> DN[DomainDescriptor]

    %% All DomainDescriptors sent to mount
    D1 & D2 & DN --> MOUNT[mount(app, *domains, prefix="/api/v1")]

    %% Steps inside mount, stacked for clarity
    MOUNT --> S1[① Register error handlers<br>(errors from all domains,<br>CORE_ERRORS, ACCESS_ERRORS)]
    S1 --> S2[② Validate all routes:<br>raise UnmarkedRouteError if<br>missing or multiple access markers]
    S2 --> S3[③ Add router with prefix<br>and OpenAPI error statuses,<br>validate Origin]
    S3 --> S4[④ Aggregate providers<br>into apps/api container]

    S4 --> FAPI[Ready FastAPI app]
```
/* The diagram visualizes how the `mount` function integrates domains (and their routers, errors, providers) into the FastAPI application through three key steps, enforces access markers, and aggregates DI providers into the apps/api container. */



1. registers error handlers of all domains plus `CORE_ERRORS`
   и `ACCESS_ERRORS`;
2. goes through all routes and falls with `UnmarkedRouteError`, if the route
   does not have an access marker or there is more than one. A route without a marker cannot
   get into the application: it simply will not be assembled;
3. connects the router with a common prefix, common error statuses in OpenAPI
   и проверкой Origin.

Providers from descriptors are aggregated into the `apps/api` container by itself.

<hr>

### `throttling/` — rate limits by client address

- `client_ip(request)` — адрес клиента из `request.client`. Реальный адрес
  there is actually, because uvicorn is run with `--proxy-headers`
  and only trusts `X-Forwarded-For` from the proxy (list in
  `apps/api/Dockerfile`), and the host nginx overwrites this header.
- `throttle_by_ip(limiter, request, bucket, limit, window_ms)` — отказ 429
  rejection 429 if exceeded and when Redis is not available.
- `throttle_by_ip_fail_open(...)` — то же, но при недоступном Redis
  passes. It is taken where a failed Redis should not crash the route:
  showcase, sections, posts, establishment of the card by the article, calendar `.ics`.
- `ThrottlingProvider` gives out `Limiter` to Redis `counters_db`.

The rate limit thresholds are kept by each domain itself, in `api/_throttle.py`.

<hr>

### `pagination/` — pages in responses

| Type | Mechanism | Where |
|---|---|---|
| `FeedPage[T]` | cursor, without `total`, `size` up to 100 | feeds: own applications, orders, notifications, posts |
| `TablePage[T]` | `limit`/`offset` (offset up to 1000) and `total` | tables of staff: queues, users, journal |

Built on `fastapi-pagination`. The cursor is marked by the sorting order
(`_cursor.py`): the cursor of one feed does not fit into another.

## How is it connected

It is not connected itself. Domains import markers, error registries,
page types and `DomainDescriptor`; `apps/api` calls `mount()`
and adds `ThrottlingProvider` through domain descriptors.

<hr>
## Tests

`packages/web/tests/`: markers and access cookie, optional identity,
Origin check, error form and error registry `core`, rate limits by address,
rate limiter provider, page types.

<hr>

