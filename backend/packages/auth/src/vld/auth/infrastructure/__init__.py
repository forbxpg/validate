"""Infrastructure of auth: ORM, mappers, stores and adapters."""

from __future__ import annotations

from ._auth_api import AuthApiAdapter
from ._clock import SystemClock
from ._hasher import BcryptPasswordHasher
from ._identity import AuthIdentityProvider
from ._jwt import JwtTokenIssuer
from ._refreshed import RedisRefreshedPairCache
from ._revocation import RedisRevocationStore
from .email import (
    ConsoleEmailSender,
    ConsoleEmailSenderInProductionError,
    EmailMisconfiguredError,
    build_smtp_sender,
)
from .models import OUTBOX, QUALIFIED_OUTBOX, SCHEMA

__all__ = (
    "OUTBOX",
    "QUALIFIED_OUTBOX",
    "SCHEMA",
    "AuthApiAdapter",
    "AuthIdentityProvider",
    "BcryptPasswordHasher",
    "ConsoleEmailSender",
    "ConsoleEmailSenderInProductionError",
    "EmailMisconfiguredError",
    "JwtTokenIssuer",
    "RedisRefreshedPairCache",
    "RedisRevocationStore",
    "SystemClock",
    "build_smtp_sender",
)
