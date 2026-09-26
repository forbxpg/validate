"""Result of a successful login."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field read at runtime
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._token_pair import TokenPair


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Result of a successful login.

    Attributes:
        user_id: uuid.UUID - Who logged in.
        pair: TokenPair - Issued tokens.
        device: str - Fresh device marker of the account.

    """

    user_id: uuid.UUID
    pair: TokenPair
    device: str
