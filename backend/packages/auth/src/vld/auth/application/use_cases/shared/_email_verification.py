"""Tokens of the links that confirm an address."""

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

_VERIFICATION_TTL = timedelta(hours=48)

# The value is random, so SHA-256 is enough to store it; no password hash needed.
_TOKEN_BYTES = 32

# Separates this derivation from the JWT signature on the same secret.
_TOKEN_INFO = b"email-verify-token:v1"


def derive_verification_token(secret: str, delivery_id: int) -> str:
    """Derive the raw token from the secret and the outbox row.

    A retried delivery of the same row sends the same link instead of a new one.

    Args:
        secret: str - `JWT_SECRET_KEY`.
        delivery_id: int - Id of the outbox row that asked for the letter.

    Returns:
        str - URL-safe token with 256 bits of entropy.

    """
    key = hmac.new(_TOKEN_INFO, secret.encode(), hashlib.sha256).digest()
    digest = hmac.new(key, str(delivery_id).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def issue_verification(
    user_id: uuid.UUID,
    now: datetime,
    *,
    raw_token: str | None = None,
) -> tuple[str, VerificationToken]:
    """Issue a one-time token that confirms an address.

    Args:
        user_id: uuid.UUID - Owner of the address.
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
        purpose=TokenPurpose.EMAIL_VERIFY,
        now=now,
        ttl=_VERIFICATION_TTL,
    )
    return raw, token
