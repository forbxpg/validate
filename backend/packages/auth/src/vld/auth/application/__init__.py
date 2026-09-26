"""Application layer of auth: ports and use cases."""

from __future__ import annotations

from .ports import (
    AccessClaims,
    Clock,
    DeviceClaims,
    EmailPermanentlyUndeliverableError,
    EmailSender,
    InvalidAccessTokenError,
    Outbox,
    PasswordHasher,
    RateLimiter,
    RefreshClaims,
    RefreshedPairCache,
    RevocationCheckUnavailableError,
    RevocationStore,
    TokenIssuer,
    TokenRepository,
    UserRepository,
    UsersPage,
)
from .use_cases import LoginResult, TokenPair

__all__ = (
    "AccessClaims",
    "Clock",
    "DeviceClaims",
    "EmailPermanentlyUndeliverableError",
    "EmailSender",
    "InvalidAccessTokenError",
    "LoginResult",
    "Outbox",
    "PasswordHasher",
    "RateLimiter",
    "RefreshClaims",
    "RefreshedPairCache",
    "RevocationCheckUnavailableError",
    "RevocationStore",
    "TokenIssuer",
    "TokenPair",
    "TokenRepository",
    "UserRepository",
    "UsersPage",
)
