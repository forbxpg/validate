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
from .models import (
    CLAIMABLE_PREDICATE,
    METADATA,
    OUTBOX,
    QUALIFIED_OUTBOX,
    SCHEMA,
    AuthBase,
    OutboxModel,
    OutboxStatus,
    UserModel,
    VerificationTokenModel,
)
from .repositories import (
    SqlAlchemyOutbox,
    SqlAlchemyTokenRepository,
    SqlAlchemyUserRepository,
)

__all__ = (
    "CLAIMABLE_PREDICATE",
    "METADATA",
    "OUTBOX",
    "QUALIFIED_OUTBOX",
    "SCHEMA",
    "AuthApiAdapter",
    "AuthBase",
    "AuthIdentityProvider",
    "BcryptPasswordHasher",
    "ConsoleEmailSender",
    "ConsoleEmailSenderInProductionError",
    "EmailMisconfiguredError",
    "JwtTokenIssuer",
    "OutboxModel",
    "OutboxStatus",
    "RedisRefreshedPairCache",
    "RedisRevocationStore",
    "SqlAlchemyOutbox",
    "SqlAlchemyTokenRepository",
    "SqlAlchemyUserRepository",
    "SystemClock",
    "UserModel",
    "VerificationTokenModel",
    "build_smtp_sender",
)
