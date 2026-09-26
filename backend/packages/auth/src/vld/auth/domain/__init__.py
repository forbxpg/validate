"""Domain layer of auth: the user aggregate, one-time tokens, events, errors."""

from __future__ import annotations

from ._enums import Role, TokenPurpose

__all__ = ("Role", "TokenPurpose")
