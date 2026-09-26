"""Mapping of a one-time token."""

from __future__ import annotations

from vld.auth.domain import VerificationToken
from vld.auth.infrastructure.models import VerificationTokenModel


def token_to_model(token: VerificationToken) -> VerificationTokenModel:
    """Build the ORM model of a token.

    Args:
        token: VerificationToken - Domain entity.

    Returns:
        VerificationTokenModel - ORM model.

    """
    return VerificationTokenModel(
        user_id=token.user_id,
        token_hash=token.token_hash,
        purpose=token.purpose,
        expires_at=token.expires_at,
        used_at=token.used_at,
    )


def token_from_model(model: VerificationTokenModel) -> VerificationToken:
    """Build the domain entity of a token.

    Args:
        model: VerificationTokenModel - ORM model.

    Returns:
        VerificationToken - Domain entity.

    """
    return VerificationToken(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        purpose=model.purpose,
        expires_at=model.expires_at,
        used_at=model.used_at,
    )
