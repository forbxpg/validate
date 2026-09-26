"""Request and response schemas of the auth HTTP layer."""

from __future__ import annotations

from ._error import AuthErrorCode, AuthErrorResponse
from ._profile import ProfileBody
from ._registration import (
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
)

__all__ = (
    "AuthErrorCode",
    "AuthErrorResponse",
    "ProfileBody",
    "RegisterRequest",
    "RegisterResponse",
    "ResendVerificationRequest",
    "VerifyEmailRequest",
)
