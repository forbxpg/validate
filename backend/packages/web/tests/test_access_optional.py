"""Optional identity on a public route: it never refuses."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import structlog
from starlette.requests import Request

from vld.web.access import ACCESS_COOKIE, Identity, optional_identity

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

VIEWER = Identity(
    user_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
    role="student",
    is_admin=False,
)


class _Refusing:
    def __init__(self, error: Exception) -> None:
        self.error: Exception = error
        self.calls: int = 0

    async def identify(self, token: str) -> Identity:
        del token
        self.calls += 1
        raise self.error


class _Accepting:
    def __init__(self) -> None:
        self.calls: int = 0

    async def identify(self, token: str) -> Identity:
        del token
        self.calls += 1
        return VIEWER


class _DomainError(Exception):
    __module__ = "vld.users.application.errors"


class _DriverError(Exception):
    params: tuple[str, ...] = ("a@b.co", "hunter2")
    statement: str = "UPDATE users SET email = %s"


def _request(token: str | None) -> Request:
    raw = [(b"cookie", f"{ACCESS_COOKIE}={token}".encode())] if token else []
    return Request({"type": "http", "headers": raw, "method": "GET", "path": "/"})


def _events(logs: Sequence[Mapping[str, object]]) -> list[tuple[object, object]]:
    return [(entry.get("event"), entry.get("log_level")) for entry in logs]


async def test_a_presented_token_names_its_owner() -> None:
    """A valid token turns into the identity of its owner."""
    provider = _Accepting()

    assert await optional_identity(_request("good"), provider) is VIEWER
    assert provider.calls == 1


async def test_no_token_does_not_ask_the_provider() -> None:
    """An anonymous visitor costs no identity lookup."""
    provider = _Accepting()

    assert await optional_identity(_request(None), provider) is None
    assert provider.calls == 0


@pytest.mark.parametrize(
    "error",
    [RuntimeError("revocation list unavailable"), ValueError("bad signature")],
    ids=["runtime_error", "value_error"],
)
async def test_any_refusal_means_anonymous(error: Exception) -> None:
    """A public page stays open whatever the provider throws."""
    provider = _Refusing(error)

    assert await optional_identity(_request("presented"), provider) is None
    assert provider.calls == 1


async def test_a_declared_refusal_is_an_info_line() -> None:
    """An expired cookie is routine and must not be logged as an error."""
    with structlog.testing.capture_logs() as logs:
        _ = await optional_identity(_request("presented"), _Refusing(_DomainError()))

    assert _events(logs) == [("optional_identity_declined", "info")]


async def test_a_broken_provider_is_an_error_line_with_its_name() -> None:
    """A bug inside the provider must be visible, not silently anonymous."""
    provider = _Refusing(AttributeError("'NoneType' object has no attribute 'jti'"))

    with structlog.testing.capture_logs() as logs:
        _ = await optional_identity(_request("presented"), provider)

    assert _events(logs) == [("optional_identity_provider_failed", "error")]
    assert logs[0]["error"] == "AttributeError"


async def test_the_presented_token_never_reaches_the_log() -> None:
    """The log is read by more people than the token was meant for."""
    secret = "eyJhbGciOiJIUzI1NiJ9.payload.signature"

    with structlog.testing.capture_logs() as logs:
        _ = await optional_identity(_request(secret), _Refusing(_DomainError()))
        _ = await optional_identity(_request(secret), _Refusing(ValueError()))

    assert len(logs) == 2
    assert all(secret not in str(entry) for entry in logs)


async def test_a_driver_error_loses_its_traceback_but_keeps_its_cause() -> None:
    """Bound SQL parameters may carry personal data, so no traceback is logged."""
    error = _DriverError("UPDATE ... [parameters: ('a@b.co', 'hunter2')]")

    with structlog.testing.capture_logs() as logs:
        _ = await optional_identity(_request("presented"), _Refusing(error))

    assert _events(logs) == [("optional_identity_provider_failed", "error")]
    assert logs[0]["exc_info"] is None
    assert logs[0]["db_error"] == "_DriverError"
