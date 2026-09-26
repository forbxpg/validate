"""Parsed claims of a device marker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class DeviceClaims:
    """Contents of a verified device marker.

    Attributes:
        user_id: uuid.UUID - Account the marker belongs to.
        issued_at: datetime - Moment of issue (`iat`).

    """

    user_id: uuid.UUID
    issued_at: datetime
