"""Domain layer of auth: the user aggregate, one-time tokens, events, errors."""

from __future__ import annotations

from ._email import normalize_email
from ._enums import Role, TokenPurpose
from ._errors import (
    AccountDeactivatedError,
    AccountGoneError,
    AuthDomainError,
    EmailAlreadyTakenError,
    EmailNotVerifiedError,
    EntityNotFoundError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from ._events import PASSWORD_RESET_REQUESTED_EVENT, USER_REGISTERED_EVENT, DomainEvent
from ._profile import Profile
from ._token import (
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenIdAlreadyAssignedError,
    VerificationToken,
)

__all__ = (
    "PASSWORD_RESET_REQUESTED_EVENT",
    "USER_REGISTERED_EVENT",
    "AccountDeactivatedError",
    "AccountGoneError",
    "AuthDomainError",
    "DomainEvent",
    "EmailAlreadyTakenError",
    "EmailNotVerifiedError",
    "EntityNotFoundError",
    "InvalidCredentialsError",
    "Profile",
    "Role",
    "TokenAlreadyUsedError",
    "TokenExpiredError",
    "TokenIdAlreadyAssignedError",
    "TokenPurpose",
    "UserNotFoundError",
    "VerificationToken",
    "normalize_email",
)
