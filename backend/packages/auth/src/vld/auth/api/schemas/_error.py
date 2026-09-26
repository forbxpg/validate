"""Contract of an auth error response: its codes and its shape."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from vld.web.errors import CoreErrorCode, ErrorDetail


class AuthErrorCode(StrEnum):
    """Machine codes of auth errors."""

    ACCOUNT_DEACTIVATED = "auth.account_deactivated"
    ACCOUNT_GONE = "auth.account_gone"
    EMAIL_ALREADY_TAKEN = "auth.email_already_taken"
    EMAIL_NOT_VERIFIED = "auth.email_not_verified"
    INTERNAL_ERROR = "auth.internal_error"
    INVALID_ACCESS_TOKEN = "auth.invalid_access_token"  # ruff: ignore[hardcoded-password-string] -- a code
    INVALID_CREDENTIALS = "auth.invalid_credentials"
    INVALID_REFRESH_TOKEN = "auth.invalid_refresh_token"  # ruff: ignore[hardcoded-password-string] -- a code
    INVALID_TOKEN = "auth.invalid_token"  # ruff: ignore[hardcoded-password-string] -- a code
    REVOCATION_CHECK_UNAVAILABLE = "auth.revocation_check_unavailable"
    TARGET_FORBIDDEN = "auth.target_forbidden"
    TOKEN_ALREADY_USED = "auth.token_already_used"  # ruff: ignore[hardcoded-password-string] -- a code
    TOKEN_EXPIRED = "auth.token_expired"  # ruff: ignore[hardcoded-password-string] -- a code
    TOKEN_REVOKED = "auth.token_revoked"  # ruff: ignore[hardcoded-password-string] -- a code
    USER_NOT_FOUND = "auth.user_not_found"
    WEAK_PASSWORD = "auth.weak_password"  # ruff: ignore[hardcoded-password-string] -- a code


class AuthErrorResponse(BaseModel):
    """Error response of auth: the common shape with a narrowed code.

    Attributes:
        error: AuthErrorCode | CoreErrorCode - Machine code.
        message: str - Text for a human.
        details: list[ErrorDetail] | None - Complaints about request fields.
        request_id: str - Id of the request.

    """

    error: AuthErrorCode | CoreErrorCode
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str
