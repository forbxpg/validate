"""Identity on a public route: asked for, never required."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from starlette.requests import Request

from vld.web.errors import db_error_kind, safe_exc_info

from ._cookie import presented_access_token

if TYPE_CHECKING:
    from ._identity import Identity, IdentityProvider


_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


_DECLARED_REFUSAL_PACKAGE = "vld."


def _is_declared_refusal(exc: Exception) -> bool:
    """Tell a refusal declared by a domain from a breakdown inside the provider.

    Args:
        exc: Exception - Caught refusal.

    Returns:
        bool - True if the exception comes from one of our packages.

    """
    return type(exc).__module__.startswith(_DECLARED_REFUSAL_PACKAGE)


async def optional_identity(
    request: Request,
    identities: IdentityProvider,
) -> Identity | None:
    """Identify the presenter of a token, or return `None` instead of refusing.

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
    except Exception as exc:  # ruff: ignore[blind-except] -- a public page never fails on identity
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
