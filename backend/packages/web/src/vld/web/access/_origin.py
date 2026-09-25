"""Checking Origin on mutating requests: CSRF at cookie transport."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from vld.core.config import get_admin_settings, get_frontend_settings

from ._cookie import ACCESS_COOKIE, REFRESH_COOKIE
from ._errors import AccessDeniedError

if TYPE_CHECKING:
    from starlette.requests import Request


_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SESSION_COOKIES = frozenset({ACCESS_COOKIE, REFRESH_COOKIE})


async def require_same_origin(request: Request) -> None:  # ruff: ignore[unused-async]
    """Reject the mutating request, coming not from our site and not from the admin.

    Args:
        request: Request - Request.

    Raises:
        AccessDeniedError: if the request mutates the state
                            and presents a foreign origin
                            or session cookies without origin at all.

    """
    if request.method not in _MUTATING_METHODS:
        return

    claimed = _claimed_origin(request)
    if claimed is None:
        if _SESSION_COOKIES & request.cookies.keys():
            msg = "mutating request carries session cookies but no origin"
            raise AccessDeniedError(msg)
        return
    if claimed not in _allowed_origins():
        msg = f"origin {claimed} is not allowed here"
        raise AccessDeniedError(msg)


def _claimed_origin(request: Request) -> str | None:
    """Determine the origin, which the request claimed itself.

    Args:
        request: Request - Request.

    Returns:
        str | None - Origin of ``https://example.com`` or ``None``,
            if the request did not claim the origin by any header.

    """
    origin = request.headers.get("Origin")
    if origin is not None:
        return origin
    referer = request.headers.get("Referer")
    if referer is None:
        return None
    return _origin_of(referer)


def _allowed_origins() -> frozenset[str]:
    """Collect both allowed origins: site and admin.

    Returns:
        frozenset[str] - One or two origins of ``https://example.com``.

    """
    origins = {_origin_of(get_frontend_settings().base_url)}
    admin = get_admin_settings().base_url
    if admin is not None:
        origins.add(_origin_of(admin))
    return frozenset(origins)


def _origin_of(url: str) -> str:
    """Cut everything from the address except the scheme and host with the port.

    Args:
        url: str - Address in full.

    Returns:
        str - Origin of ``https://example.com``.

    """
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
