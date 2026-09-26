"""Ports of the auth domain, one module per port."""

from __future__ import annotations

from ._access_claims import AccessClaims
from ._clock import Clock
from ._device_claims import DeviceClaims
from ._email_sender import EmailPermanentlyUndeliverableError, EmailSender
from ._outbox import Outbox
from ._password_hasher import PasswordHasher
from ._rate_limiter import RateLimiter
from ._refresh_claims import RefreshClaims
from ._token_issuer import InvalidAccessTokenError, TokenIssuer

__all__ = (
    "AccessClaims",
    "Clock",
    "DeviceClaims",
    "EmailPermanentlyUndeliverableError",
    "EmailSender",
    "InvalidAccessTokenError",
    "Outbox",
    "PasswordHasher",
    "RateLimiter",
    "RefreshClaims",
    "TokenIssuer",
)
