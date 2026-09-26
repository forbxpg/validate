"""Normalization of an email address."""

from __future__ import annotations


def normalize_email(email: str) -> str:
    """Bring an address to the form it is stored and compared in.

    Args:
        email: str - Address as the user typed it.

    Returns:
        str - The address without surrounding spaces, in lower case.

    """
    return email.strip().lower()
