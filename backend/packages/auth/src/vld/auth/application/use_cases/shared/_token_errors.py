"""Refusal of a one-time token from a letter."""

from __future__ import annotations

from vld.auth.domain import AuthDomainError


class InvalidTokenError(AuthDomainError):
    """The token is unknown."""
