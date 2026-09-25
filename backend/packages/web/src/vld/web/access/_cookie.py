"""Access tokens in cookies: browser transport."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request

from ._bearer_token import bearer
from ._errors import NotAuthenticatedError

if TYPE_CHECKING:
    from starlette.responses import Response


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
    *,
    access: str,
    access_max_age: int,
    refresh: str,
    refresh_max_age: int,
) -> None:
    """Set both session cookies on the response.

    Args:
        response: Response - Response the cookies are set on.
        access: str - Access token.
        access_max_age: int - Access cookie lifetime in seconds.
        refresh: str - Refresh token.
        refresh_max_age: int - Refresh cookie lifetime in seconds.

    """
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=access_max_age,
        path=COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=refresh_max_age,
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
