"""Determination of the client address: knowledge of the transport, proxy and NAT."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from starlette.requests import Request


_UNKNOWN_CLIENT = "unknown"

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)

_warned_unknown_client = False


def client_ip(request: Request) -> str:
    """Determine the client address.

    Args:
        request: Request - Request.

    Returns:
        str - Client address or ``unknown``, if the transport did not report it.

    """
    if request.client is not None:
        return request.client.host
    global _warned_unknown_client  # ruff: ignore[global-statement] -- lock «warn once»
    if not _warned_unknown_client:
        _warned_unknown_client = True
        _log.warning(
            "client_address_unknown",
            hint=(
                "транспорт не сообщает адрес клиента (unix-сокет?); "
                "все клиенты делят один бакет лимитера — лимит по IP "
                "фактически стал глобальным лимитом на сервис"
            ),
        )
    return _UNKNOWN_CLIENT
