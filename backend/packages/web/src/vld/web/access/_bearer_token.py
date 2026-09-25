"""Parsing `Authorization: Bearer <token>` — client transport."""

from __future__ import annotations

from starlette.requests import Request

from ._errors import NotAuthenticatedError

_BEARER = "Bearer "


def bearer(request: Request) -> str:
    """Get the token from the `Authorization` header.

    Args:
        request: Request - Request.

    Returns:
        str - Presented token.

    Raises:
        NotAuthenticatedError: if the header is missing, it's not the right scheme or
            the token is empty.

    """
    header = request.headers.get("Authorization")
    token = (
        header.removeprefix(_BEARER).strip()
        if header is not None and header.startswith(_BEARER)
        else ""
    )
    if not token:
        msg = "bearer token is required"
        raise NotAuthenticatedError(msg)
    return token
