"""Tokens of the links that set a new password."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

from vld.auth.domain import TokenPurpose, VerificationToken

from ._token_hashing import hash_token

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

# One hour: while the link lives, access to the mailbox equals access to the account.
_PASSWORD_RESET_TTL = timedelta(hours=1)

_TOKEN_BYTES = 32

# Must differ from the confirmation label, or a confirmation link would reset passwords.
_TOKEN_INFO = b"password-reset-token:v1"


def derive_password_reset_token(secret: str, delivery_id: int) -> str:
    """Derive the raw reset token from the secret and the outbox row.

    Args:
        secret: str - `JWT_SECRET_KEY`.
        delivery_id: int - Id of the outbox row that asked for the letter.

    Returns:
        str - URL-safe token with 256 bits of entropy.

    """
    key = hmac.new(_TOKEN_INFO, secret.encode(), hashlib.sha256).digest()
    digest = hmac.new(key, str(delivery_id).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def issue_password_reset(
    user_id: uuid.UUID,
    now: datetime,
    *,
    raw_token: str | None = None,
) -> tuple[str, VerificationToken]:
    """Issue a one-time token that sets a new password.

    Args:
        user_id: uuid.UUID - Account whose password is reset.
        now: datetime - Moment of issue.
        raw_token: str | None - Ready raw value, or None for a random one.

    Returns:
        tuple[str, VerificationToken] - Raw token for the letter and the stored
            form, which keeps only the hash.

    """
    raw = secrets.token_urlsafe(_TOKEN_BYTES) if raw_token is None else raw_token
    token = VerificationToken.issue(
        user_id=user_id,
        token_hash=hash_token(raw),
        purpose=TokenPurpose.PASSWORD_RESET,
        now=now,
        ttl=_PASSWORD_RESET_TTL,
    )
    return raw, token
