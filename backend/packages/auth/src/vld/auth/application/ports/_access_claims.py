"""Parsed claims of an access token."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class AccessClaims:
    """Contents of a verified access token.

    Attributes:
        user_id: uuid.UUID - Owner.
        jti: str - Token id, the key of the revocation list.
        issued_at: datetime - Moment of issue (`iat`).

    """

    user_id: uuid.UUID
    jti: str
    issued_at: datetime
