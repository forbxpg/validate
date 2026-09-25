"""Token transport: the browser cookie against the header of a program."""

from __future__ import annotations

import pytest
from fastapi import Response
from starlette.requests import Request

from vld.web.access import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    NotAuthenticatedError,
    access_token,
    clear_session_cookies,
    presented_access_token,
    set_session_cookies,
)

ACCESS_MAX_AGE = 15 * 60
REFRESH_MAX_AGE = 30 * 24 * 60 * 60


def _request(
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Request:
    raw = [
        (name.lower().encode(), value.encode())
        for name, value in (headers or {}).items()
    ]
    if cookies:
        jar = "; ".join(f"{name}={value}" for name, value in cookies.items())
        raw.append((b"cookie", jar.encode()))
    return Request({"type": "http", "headers": raw, "method": "POST", "path": "/"})


def _set_cookie_headers(response: Response) -> dict[str, list[str]]:
    return {
        raw.split("=", 1)[0]: raw.split("; ")
        for key, value in response.raw_headers
        if key == b"set-cookie"
        for raw in [value.decode()]
    }


def test_the_cookie_wins_over_the_header() -> None:
    """A browser presents a cookie, a program presents a header."""
    request = _request(
        cookies={ACCESS_COOKIE: "from-cookie"},
        headers={"Authorization": "Bearer from-header"},
    )

    assert access_token(request) == "from-cookie"


def test_a_program_still_authenticates_with_a_header() -> None:
    """The API has clients besides the browser."""
    request = _request(headers={"Authorization": "Bearer from-header"})

    assert access_token(request) == "from-header"


def test_a_blank_cookie_without_a_header_is_refused() -> None:
    """An empty cookie is no token, not an empty token."""
    with pytest.raises(NotAuthenticatedError):
        _ = access_token(_request(cookies={ACCESS_COOKIE: "   "}))


def test_no_token_is_none_for_a_caller_that_does_not_require_one() -> None:
    """Logout must work after the access token has expired."""
    assert presented_access_token(_request()) is None


def test_session_cookies_are_out_of_reach_for_scripts() -> None:
    """HttpOnly, Secure and SameSite are the reason the tokens live in cookies."""
    response = Response()

    set_session_cookies(
        response,
        access="a-token",
        access_max_age=ACCESS_MAX_AGE,
        refresh="r-token",
        refresh_max_age=REFRESH_MAX_AGE,
    )

    cookies = _set_cookie_headers(response)
    assert cookies.keys() == {ACCESS_COOKIE, REFRESH_COOKIE}
    for attributes in cookies.values():
        assert {"HttpOnly", "Secure", "SameSite=lax", "Path=/api"} <= set(attributes)
    assert f"Max-Age={ACCESS_MAX_AGE}" in cookies[ACCESS_COOKIE]
    assert f"Max-Age={REFRESH_MAX_AGE}" in cookies[REFRESH_COOKIE]


def test_logout_removes_the_cookies_with_the_same_attributes() -> None:
    """A cookie is matched by name and path: clearing it on `/` would miss `/api`."""
    response = Response()

    clear_session_cookies(response)

    cookies = _set_cookie_headers(response)
    assert cookies.keys() == {ACCESS_COOKIE, REFRESH_COOKIE}
    for attributes in cookies.values():
        assert {"Max-Age=0", "HttpOnly", "Secure", "SameSite=lax", "Path=/api"} <= set(
            attributes
        )
