"""Determining the client address."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from starlette.requests import Request


_UNKNOWN_CLIENT = "unknown"

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


def client_ip(request: Request) -> str:
    """Determine the client address.

    Args:
        request: Request - Request.

    Returns:
        str - Client address, or ``unknown`` if the transport did not report it.

    """
    if request.client is not None:
        return request.client.host
    _warn_unknown_client()
    return _UNKNOWN_CLIENT


@cache
def _warn_unknown_client() -> None:
    """Warn once per process that every client shares one bucket."""
    _log.warning(
        "client_address_unknown",
        hint=(
            "the transport does not report the client address (unix socket?); "
            "all clients share one limiter bucket, so the per-IP limit "
            "has become a global limit on the service"
        ),
    )
