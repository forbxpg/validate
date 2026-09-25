"""Origin check on mutating requests: CSRF protection for the cookie transport."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

from starlette.requests import Request

from vld.core.config import CorsSettings

from ._cookie import ACCESS_COOKIE, REFRESH_COOKIE
from ._errors import AccessDeniedError

if TYPE_CHECKING:
    from dishka import AsyncContainer


_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SESSION_COOKIES = frozenset({ACCESS_COOKIE, REFRESH_COOKIE})


async def require_same_origin(request: Request) -> None:
    """Refuse a mutating request that comes from an untrusted origin.

    Args:
        request: Request - Request.

    Raises:
        AccessDeniedError: If the request mutates state and claims an untrusted
            origin, or carries session cookies without claiming any origin.

    """
    if request.method not in _MUTATING_METHODS:
        return

    claimed = _claimed_origin(request)
    if claimed is None:
        if _SESSION_COOKIES & request.cookies.keys():
            msg = "mutating request carries session cookies but no origin"
            raise AccessDeniedError(msg)
        return

    container = cast("AsyncContainer", request.state.dishka_container)
    settings = await container.get(CorsSettings)
    if claimed not in settings.allowed_origins:
        msg = f"origin {claimed} is not allowed here"
        raise AccessDeniedError(msg)


def _claimed_origin(request: Request) -> str | None:
    """Determine the origin the request claims.

    Args:
        request: Request - Request.

    Returns:
        str | None - Origin such as ``https://example.com``, or ``None`` if neither
            `Origin` nor `Referer` is present.

    """
    origin = request.headers.get("Origin")
    if origin is not None:
        return origin
    referer = request.headers.get("Referer")
    if referer is None:
        return None
    parts = urlsplit(referer)
    return f"{parts.scheme}://{parts.netloc}"
