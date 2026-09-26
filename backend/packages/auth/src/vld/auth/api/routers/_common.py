"""Shared by the auth routers: cookies and the error statuses of the domain."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from vld.auth.api.schemas import AuthErrorResponse
from vld.web.access import COOKIE_PATH, set_session_cookies

if TYPE_CHECKING:
    from fastapi import Response

    from vld.auth.application import TokenPair
    from vld.auth.config import JwtSettings


# Authorizes nothing; it only lets a known device past the per-email login limit.
DEVICE_COOKIE = "validate_device"
_DEVICE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60

# Only the statuses of the domain; mounting adds the common ones.
ERROR_RESPONSES: dict[int | str, dict[str, type[AuthErrorResponse]]] = {
    HTTPStatus.BAD_REQUEST: {"model": AuthErrorResponse},
    HTTPStatus.UNAUTHORIZED: {"model": AuthErrorResponse},
    HTTPStatus.FORBIDDEN: {"model": AuthErrorResponse},
    HTTPStatus.NOT_FOUND: {"model": AuthErrorResponse},
    HTTPStatus.CONFLICT: {"model": AuthErrorResponse},
}


def set_device_cookie(response: Response, token: str) -> None:
    """Set the httpOnly cookie of the device marker.

    Args:
        response: Response - Response the cookie is set on.
        token: str - Fresh device marker of the logged-in account.

    """
    response.set_cookie(
        DEVICE_COOKIE,
        token,
        max_age=_DEVICE_COOKIE_MAX_AGE,
        path=COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="lax",
    )


def set_pair_cookies(
    response: Response,
    pair: TokenPair,
    settings: JwtSettings,
) -> None:
    """Set both session cookies, each living as long as its token.

    Args:
        response: Response - Response the cookies are set on.
        pair: TokenPair - Issued tokens.
        settings: JwtSettings - Lifetimes of the tokens.

    """
    set_session_cookies(
        response,
        access=pair.access,
        access_max_age=int(settings.access_ttl.total_seconds()),
        refresh=pair.refresh,
        refresh_max_age=int(settings.refresh_ttl.total_seconds()),
    )
