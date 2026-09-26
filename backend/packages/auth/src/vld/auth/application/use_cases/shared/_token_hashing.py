"""Hashing one-time tokens for storage."""

from __future__ import annotations

import hashlib


def hash_token(raw: str) -> str:
    """Hash a token value for storage.

    Args:
        raw: str - Value sent to the user.

    Returns:
        str - Hex SHA-256.

    """
    return hashlib.sha256(raw.encode()).hexdigest()
