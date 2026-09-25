"""Opaque request identifier, the only support for support."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, override

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response


REQUEST_ID_HEADER_NAME = "X-Request-Id"
_REQUEST_ID_PATTERN = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")
_STATE_ATTR = "request_id"


def _resolve(incoming: str | None) -> str:
    """Take the incoming identifier or release your own.

    Args:
        incoming: str | None - The value of the request header.

    Returns:
        str - Suitable for logging identifier.

    """
    if incoming is not None and _REQUEST_ID_PATTERN.match(incoming):
        return incoming
    return uuid.uuid4().hex


def get_request_id(request: Request) -> str:
    """Get the identifier of the current request.

    Args:
        request: Request - Request.

    Returns:
        str - Request identifier.

    """
    existing = getattr(request.state, _STATE_ATTR, None)
    return existing if isinstance(existing, str) else _resolve(None)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns an identifier to the request, puts it in the log and in the header."""

    @override
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Add an identifier before processing and return it to the client.

        Args:
            request: Request - Request.
            call_next: RequestResponseEndpoint - Remaining chain of processing.

        Returns:
            Response - Response with the header ``X-Request-Id``.

        """
        request_id = _resolve(request.headers.get(REQUEST_ID_HEADER_NAME))
        setattr(request.state, _STATE_ATTR, request_id)
        # Clear before, not only after: the worker reuses the context, and
        # an unclean binding would stick the identifier of another request.
        structlog.contextvars.clear_contextvars()
        _ = structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[REQUEST_ID_HEADER_NAME] = request_id
        return response
