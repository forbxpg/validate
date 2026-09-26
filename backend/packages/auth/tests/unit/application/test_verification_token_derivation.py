"""Deriving the confirmation token from the delivery id."""

from __future__ import annotations

import base64
import hashlib
import hmac

from vld.auth.application.use_cases.shared._email_verification import (
    derive_verification_token,
)

_SECRET = "x" * 32


def test_same_delivery_gives_the_same_token() -> None:
    """One delivery id gives one token, so a retry sends the same link."""
    assert derive_verification_token(_SECRET, 42) == derive_verification_token(
        _SECRET,
        42,
    )


def test_different_deliveries_give_different_tokens() -> None:
    """Different deliveries give different tokens."""
    assert derive_verification_token(_SECRET, 42) != derive_verification_token(
        _SECRET,
        43,
    )


def test_different_secrets_give_different_tokens() -> None:
    """The secret takes part in the derivation."""
    assert derive_verification_token(_SECRET, 42) != derive_verification_token(
        "y" * 32,
        42,
    )


def test_key_is_separated_from_the_signing_secret() -> None:
    """The derivation key is not the JWT signing secret."""
    digest = hmac.new(_SECRET.encode(), b"42", hashlib.sha256).digest()
    naive = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert derive_verification_token(_SECRET, 42) != naive


def test_token_is_url_safe_and_long_enough() -> None:
    """The token fits a link and carries 256 bits."""
    # Fits a link in a letter and carries 256 bits.
    token = derive_verification_token(_SECRET, 1)
    assert len(token) >= 43
    assert set(token) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
    )
