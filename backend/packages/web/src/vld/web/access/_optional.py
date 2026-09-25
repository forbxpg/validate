"""Личность там, где её спрашивают, но не требуют: публичный маршрут."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from vld.web.errors import db_error_kind, safe_exc_info

from ._cookie import presented_access_token

if TYPE_CHECKING:
    from starlette.requests import Request

    from ._identity import Identity, IdentityProvider


_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


_DECLARED_REFUSAL_PACKAGE = "vld.web."


def _is_declared_refusal(exc: Exception) -> bool:
    """Is this refusal declared by the domain — or is it a breakdown inside the provider.

    Args:
        exc: Exception - Caught refusal.

    Returns:
        bool - True, if the refusal is declared by the domain, that is, stated.

    """
    return type(exc).__module__.startswith(_DECLARED_REFUSAL_PACKAGE)


async def optional_identity(
    request: Request,
    identities: IdentityProvider,
) -> Identity | None:
    """Set the identity of the presenter, but do not refuse if it did not work out.

    Args:
        request: Request - Request; from it the presented token is taken.
        identities: IdentityProvider - Establishing identity by the token.

    Returns:
        Identity | None - Presenter or ``None``.

    """
    token = presented_access_token(request)
    if token is None:
        return None
    try:
        return await identities.identify(token)
    except Exception as exc:  # ruff: ignore[blind-except]
        if _is_declared_refusal(exc):
            _log.info("optional_identity_declined", error=type(exc).__qualname__)
        else:
            _log.error(
                "optional_identity_provider_failed",
                error=type(exc).__qualname__,
                db_error=db_error_kind(exc),
                exc_info=safe_exc_info(exc),
            )
        return None
