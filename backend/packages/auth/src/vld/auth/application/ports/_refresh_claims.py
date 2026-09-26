"""Parsed claims of a refresh token."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class RefreshClaims:
    """Contents of a verified refresh token.

    Attributes:
        user_id: uuid.UUID - Owner.
        jti: str - Token id.
        issued_at: datetime - Moment of issue (`iat`), compared with
            `tokens_invalidated_after`.
        session_exp: datetime - Absolute ceiling of the session; a refresh carries
            it into the new pair unchanged.

    """

    user_id: uuid.UUID
    jti: str
    issued_at: datetime
    session_exp: datetime
