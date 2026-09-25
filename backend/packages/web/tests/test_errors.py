"""The single error form: what reaches the client and what never does."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from structlog.contextvars import merge_contextvars
from structlog.testing import capture_logs

from vld.core.ratelimit import RateLimitExceededError
from vld.web.errors import (
    CORE_ERRORS,
    REQUEST_ID_HEADER_NAME,
    ErrorRegistry,
    ErrorSpec,
    RequestIdMiddleware,
    register_error_handlers,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

LEAKY_EXCEPTION_TEXT = "user 4f1c-victim@example.com already exists"


class _BoomError(Exception): ...


class _MappedError(_BoomError): ...


class _UnmappedError(_BoomError): ...


class _DelayedError(_BoomError): ...


TEST_ERRORS = ErrorRegistry(
    base=_BoomError,
    fallback_code="test.internal_error",
    mapping={
        _MappedError: ErrorSpec(
            status=409,
            code="test.mapped",
            message="Already taken.",
        ),
        _DelayedError: ErrorSpec(
            status=503,
            code="test.delayed",
            message="Try again later.",
            retry_after=7,
        ),
    },
)


class _Credentials(BaseModel):
    email: str
    password: str


async def _mapped() -> None:
    raise _MappedError(LEAKY_EXCEPTION_TEXT)


async def _unmapped() -> None:
    raise _UnmappedError(LEAKY_EXCEPTION_TEXT)


async def _delayed() -> None:
    raise _DelayedError(LEAKY_EXCEPTION_TEXT)


async def _throttled() -> None:
    raise RateLimitExceededError(retry_after=42)


async def _login(body: _Credentials) -> None:
    del body


async def _noisy() -> None:
    structlog.stdlib.get_logger("elsewhere").info("deep_inside")
    raise _MappedError(LEAKY_EXCEPTION_TEXT)


async def _rogue() -> None:
    msg = "something no registry knows about"
    raise RuntimeError(msg)


ACCOUNT_NUMBER = "40702810000000000001"


class _StatementShapedError(Exception):
    statement: str = "UPDATE users SET passport_number=%(p)s"
    params: ClassVar[dict[str, str]] = {"p": ACCOUNT_NUMBER}
    orig: Exception = ValueError("server closed the connection")


async def _db_failure() -> None:
    msg = (
        "(builtins.ValueError) server closed the connection "
        f"[SQL: UPDATE ...] [parameters: {{'p': '{ACCOUNT_NUMBER}'}}]"
    )
    raise _StatementShapedError(msg)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app, TEST_ERRORS, CORE_ERRORS)
    _ = app.get("/mapped")(_mapped)
    _ = app.get("/unmapped")(_unmapped)
    _ = app.get("/delayed")(_delayed)
    _ = app.get("/throttled")(_throttled)
    _ = app.post("/login")(_login)
    _ = app.get("/noisy")(_noisy)
    _ = app.get("/rogue")(_rogue)
    _ = app.get("/db-failure")(_db_failure)
    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Serve an app with the request id middleware and both registries."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_mapped_error_takes_status_and_text_from_the_table(
    client: AsyncClient,
) -> None:
    """A mapped domain error gets the status and text of its table entry."""
    response = await client.get("/mapped")

    assert response.status_code == 409
    assert response.json()["error"] == "test.mapped"
    assert response.json()["message"] == "Already taken."


async def test_unmapped_error_is_500_and_not_a_plausible_400(
    client: AsyncClient,
) -> None:
    """A default that looks like it works is how a table silently rots."""
    response = await client.get("/unmapped")

    assert response.status_code == 500
    assert response.json()["error"] == "test.internal_error"


async def test_exception_text_never_reaches_the_body(client: AsyncClient) -> None:
    """`str(exc)` carries addresses, ids and constraint names."""
    for path in ("/mapped", "/unmapped", "/delayed"):
        response = await client.get(path)
        assert LEAKY_EXCEPTION_TEXT not in response.text
        assert "victim@example.com" not in response.text


async def test_retry_after_comes_from_the_table(client: AsyncClient) -> None:
    """A table entry may invite the client to retry later."""
    response = await client.get("/delayed")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "7"


async def test_rate_limit_error_from_core_is_mapped_not_500(
    client: AsyncClient,
) -> None:
    """The limiter error from core has its own registry."""
    response = await client.get("/throttled")

    assert response.status_code == 429
    assert response.json()["error"] == "core.rate_limit_exceeded"


async def test_own_retry_after_wins_over_the_table(client: AsyncClient) -> None:
    """The limiter knows the rest of its window; a constant would lie."""
    response = await client.get("/throttled")

    assert response.headers["Retry-After"] == "42"


async def test_validation_error_has_the_same_shape(client: AsyncClient) -> None:
    """Otherwise a client handles two incompatible error forms."""
    response = await client.post("/login", json={"email": "a@b.co"})
    body = cast("dict[str, object]", response.json())

    assert response.status_code == 422
    assert body["error"] == "core.validation_failed"
    assert body["request_id"]
    assert "detail" not in body
    assert body["details"] == [{"field": "body.password", "message": "Field required"}]


async def test_validation_error_does_not_echo_the_submitted_password(
    client: AsyncClient,
) -> None:
    """`exc.errors()` carries the input, which on login is the password."""
    response = await client.post(
        "/login",
        json={"email": "a@b.co", "password": ["hunter2"]},
    )

    assert response.status_code == 422
    assert "hunter2" not in response.text


async def test_request_id_is_echoed_and_returned(client: AsyncClient) -> None:
    """A good incoming request id is kept for the whole request."""
    response = await client.get(
        "/mapped", headers={REQUEST_ID_HEADER_NAME: "trace-123"}
    )

    assert response.json()["request_id"] == "trace-123"
    assert response.headers[REQUEST_ID_HEADER_NAME] == "trace-123"


async def test_hostile_request_id_is_replaced(client: AsyncClient) -> None:
    """The id goes into logs, so spaces and length are refused."""
    response = await client.get("/mapped", headers={REQUEST_ID_HEADER_NAME: "a " * 200})
    assert response.json()["request_id"] != "a " * 200
    assert " " not in response.json()["request_id"]


async def test_error_response_is_never_cached(client: AsyncClient) -> None:
    """The body carries the id of one particular request."""
    response = await client.get("/mapped")
    assert response.headers["Cache-Control"] == "no-store"


async def test_every_error_response_is_logged_with_its_request_id(
    client: AsyncClient,
) -> None:
    """Support finds the request in the logs by the id the user saw."""
    with capture_logs(processors=[merge_contextvars]) as logs:
        response = await client.get(
            "/mapped", headers={REQUEST_ID_HEADER_NAME: "trace-abc"}
        )

    assert response.json()["request_id"] == "trace-abc"
    assert any(entry.get("request_id") == "trace-abc" for entry in logs)


async def test_request_id_reaches_logs_of_unrelated_code(client: AsyncClient) -> None:
    """The id is bound to the context, not written into one record."""
    with capture_logs(processors=[merge_contextvars]) as logs:
        _ = await client.get("/noisy", headers={REQUEST_ID_HEADER_NAME: "trace-xyz"})

    noisy = [entry for entry in logs if entry["event"] == "deep_inside"]

    assert len(noisy) == 1
    assert noisy[0].get("request_id") == "trace-xyz"


async def test_unregistered_exception_still_gets_the_single_form() -> None:
    """An unexpected error still answers in the single form."""
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/rogue")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"] == "core.internal_error"
    assert response.json()["request_id"]


async def test_request_id_header_survives_an_unhandled_exception() -> None:
    """The header and the body carry the same id on the crash path too."""
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/rogue", headers={REQUEST_ID_HEADER_NAME: "trace-rogue"}
        )

    assert response.headers[REQUEST_ID_HEADER_NAME] == "trace-rogue"
    assert response.json()["request_id"] == "trace-rogue", (
        "the header and the body must carry one id"
    )


async def test_server_errors_are_logged_at_error_level() -> None:
    """A 5xx is logged as an error, not as info."""
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    with capture_logs() as logs:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            _ = await ac.get("/rogue")

    rendered = [entry for entry in logs if entry["event"] == "http_error_response"]
    assert rendered, "an error response must be logged"
    assert all(entry["log_level"] == "error" for entry in rendered), rendered


async def test_unknown_path_uses_the_single_form(client: AsyncClient) -> None:
    """A 404 does not fall back to the framework `detail` form."""
    response = await client.get("/nothing-here")

    assert response.status_code == 404
    assert "detail" not in response.json()
    assert response.json()["error"] == "core.http_error"


async def test_body_and_log_agree_even_without_the_middleware() -> None:
    """The body and the log share the id even without the middleware."""
    app = FastAPI()
    register_error_handlers(app, TEST_ERRORS, CORE_ERRORS)
    _ = app.get("/mapped")(_mapped)
    transport = ASGITransport(app=app)
    with capture_logs(processors=[merge_contextvars]) as logs:
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            response = await ac.get("/mapped")
    responses = [e for e in logs if e["event"] == "http_error_response"]
    assert len(responses) == 1
    assert responses[0].get("request_id") == response.json()["request_id"]


async def test_bound_parameters_never_reach_the_log() -> None:
    """Values bound to SQL must not leak into the log through a traceback."""
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    with capture_logs(processors=[merge_contextvars]) as logs:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/db-failure")
    assert response.status_code == 500
    assert ACCOUNT_NUMBER not in response.text
    assert logs, "the error must be logged"
    assert ACCOUNT_NUMBER not in repr(logs)


async def test_cause_of_a_database_failure_stays_visible() -> None:
    """Without the traceback the log still names the cause."""
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    with capture_logs(processors=[merge_contextvars]) as logs:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            _ = await ac.get("/db-failure")
    assert any(entry.get("db_error") == "ValueError" for entry in logs)


async def test_ordinary_failures_keep_their_traceback() -> None:
    """Ordinary errors keep their full traceback."""
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    with capture_logs(processors=[merge_contextvars]) as logs:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            _ = await ac.get("/rogue")
    assert any(entry.get("exc_info") for entry in logs)
