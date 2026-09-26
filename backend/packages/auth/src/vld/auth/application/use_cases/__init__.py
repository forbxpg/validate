"""Use cases of auth, one module per use case, grouped by process."""

from __future__ import annotations

from .onboarding._register import RegisterCommand, RegisterUser
from .onboarding._resend_verification import (
    ResendVerification,
    ResendVerificationCommand,
)
from .onboarding._send_password_reset_email import (
    SendPasswordResetEmail,
    UnknownResetTargetError,
)
from .onboarding._send_verification_email import (
    SendVerificationEmail,
    UnknownRegisteredUserError,
)
from .onboarding._verify_email import VerifyEmail
from .session._dummy_hash import warm_password_verification
from .shared import InvalidTokenError, LoginResult, TokenPair, WeakPasswordError

__all__ = (
    "InvalidTokenError",
    "LoginResult",
    "RegisterCommand",
    "RegisterUser",
    "ResendVerification",
    "ResendVerificationCommand",
    "SendPasswordResetEmail",
    "SendVerificationEmail",
    "TokenPair",
    "UnknownRegisteredUserError",
    "UnknownResetTargetError",
    "VerifyEmail",
    "WeakPasswordError",
    "warm_password_verification",
)
