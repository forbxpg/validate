"""Issued tokens, shared by login and refresh."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenPair:
    """An issued pair of tokens.

    Attributes:
        access: str - Short-lived access token.
        refresh: str - Refresh token.

    """

    access: str
    refresh: str
