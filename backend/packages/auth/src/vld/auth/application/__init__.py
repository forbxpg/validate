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
from .use_cases import (
    InvalidTokenError,
    LoginResult,
    RegisterCommand,
    RegisterUser,
    TokenPair,
    VerifyEmail,
    WeakPasswordError,
)

__all__ = (
    "AccessClaims",
    "Clock",
    "DeviceClaims",
    "EmailPermanentlyUndeliverableError",
    "EmailSender",
    "InvalidAccessTokenError",
    "InvalidTokenError",
    "LoginResult",
    "Outbox",
    "PasswordHasher",
    "RateLimiter",
    "RefreshClaims",
    "RefreshedPairCache",
    "RegisterCommand",
    "RegisterUser",
    "RevocationCheckUnavailableError",
    "RevocationStore",
    "TokenIssuer",
    "TokenPair",
    "TokenRepository",
    "UserRepository",
    "UsersPage",
    "VerifyEmail",
    "WeakPasswordError",
)
