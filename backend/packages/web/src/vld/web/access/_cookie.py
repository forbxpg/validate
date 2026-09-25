"""Access tokens in cookies: browser transport."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._bearer_token import bearer
from ._errors import NotAuthenticatedError

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

    from vld.core.config import SecuritySettings


ACCESS_COOKIE = "validate_access"
REFRESH_COOKIE = "validate_refresh"
COOKIE_PATH = "/api"


def presented_access_token(request: Request) -> str | None:
    """Get the access token, if it is presented: first cookie, then header.

    Args:
        request: Request - Request.

    Returns:
        str | None - Presented token or `None` if it is not in the cookie or header.

    """
    from_cookie = request.cookies.get(ACCESS_COOKIE, "").strip()
    if from_cookie:
        return from_cookie
    try:
        return bearer(request)
    except NotAuthenticatedError:
        return None


def access_token(request: Request) -> str:
    """Get the access token: first cookie, then header.

    Args:
        request: Request - Request.

    Returns:
        str - Presented token.

    Raises:
        NotAuthenticatedError: if the token is not in the cookie or header.

    """
    token = presented_access_token(request)
    if token is None:
        msg = "access token is required"
        raise NotAuthenticatedError(msg)
    return token


def set_session_cookies(
    response: Response,
    settings: SecuritySettings,
    *,
    access: str,
    refresh: str,
) -> None:
    """Set both session cookies on the response.

    Args:
        response: Response - Response, in which the cookies are set.
        settings: SecuritySettings - Token lifetimes.
        access: str - Access token.
        refresh: str - Refresh token.

    """
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.access_ttl_seconds,
        path=COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_ttl_seconds,
        path=COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="lax",
    )


def clear_session_cookies(response: Response) -> None:
    """Clear both session cookies.

    Args:
        response: Response - Response, in which the cookies are cleared.

    """
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(
            name,
            path=COOKIE_PATH,
            httponly=True,
            secure=True,
            samesite="lax",
        )
