"""Pieces shared by the use cases of several processes."""

from __future__ import annotations

from ._email_bucket import email_bucket_key, email_sha256
from ._email_verification import derive_verification_token, issue_verification
from ._login_result import LoginResult
from ._password_policy import WeakPasswordError, check_password
from ._token_errors import InvalidTokenError
from ._token_hashing import hash_token
from ._token_pair import TokenPair

__all__ = (
    "InvalidTokenError",
    "LoginResult",
    "TokenPair",
    "WeakPasswordError",
    "check_password",
    "derive_verification_token",
    "email_bucket_key",
    "email_sha256",
    "hash_token",
    "issue_verification",
)
