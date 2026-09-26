"""Schemas of reading the audit log."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditRecordResponse(BaseModel):
    """One record of the log.

    Attributes:
        id: int - Record number.
        occurred_at: datetime - When it happened; set by the database.
        action: str - What happened.
        actor_id: uuid.UUID | None - Who did it.
        target_id: uuid.UUID | None - Over whose account.
        payload: dict[str, str] - Payload of the record.

    """

    id: int
    occurred_at: datetime
    action: str
    actor_id: uuid.UUID | None
    target_id: uuid.UUID | None
    payload: dict[str, str]
