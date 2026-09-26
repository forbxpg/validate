"""Request and response schemas of the auth HTTP layer."""

from __future__ import annotations

from ._account import MeResponse
from ._administration import AdminUserResponse, ChangeRoleRequest, SetActiveRequest
from ._error import AuthErrorCode, AuthErrorResponse
from ._password import ChangePasswordRequest, NewPasswordRequest, PasswordResetRequest
from ._profile import ProfileBody
from ._registration import (
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from ._sessions import (
    LoginRequest,
    RefreshRequest,
    SessionRefreshedResponse,
    TokenPairResponse,
)

__all__ = (
    "AdminUserResponse",
    "AuthErrorCode",
    "AuthErrorResponse",
    "ChangePasswordRequest",
    "ChangeRoleRequest",
    "LoginRequest",
    "MeResponse",
    "NewPasswordRequest",
    "PasswordResetRequest",
    "ProfileBody",
    "RefreshRequest",
    "RegisterRequest",
    "RegisterResponse",
    "ResendVerificationRequest",
    "SessionRefreshedResponse",
    "SetActiveRequest",
    "TokenPairResponse",
    "VerifyEmailRequest",
)
