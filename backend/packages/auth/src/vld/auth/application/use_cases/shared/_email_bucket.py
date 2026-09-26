"""An address in a form that can be matched but not read back."""

from __future__ import annotations

import hashlib

from vld.auth.domain import normalize_email


def email_sha256(email: str) -> str:
    """Hash an address so it can be matched without being stored.

    Args:
        email: str - Address as typed.

    Returns:
        str - Hex SHA-256 of the normalized address.

    """
    return hashlib.sha256(normalize_email(email).encode()).hexdigest()


def email_bucket_key(action: str, email: str) -> str:
    """Build the limiter key of an address without storing the address itself.

    Args:
        action: str - What is limited, e.g. `login`.
        email: str - Address as typed.

    Returns:
        str - Key such as `login:email:<sha256>`.

    """
    return f"{action}:email:{email_sha256(email)}"
