"""Audit entry — generalized, without domain knowledge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from ._action import AuditAction


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One auditable event.

    Attributes:
        action: AuditAction - What happened.
        actor_id: uuid.UUID | None - Who did it.
        target_id: uuid.UUID | None - Over whose account.
        payload: dict[str, str] - Everything else that needs to be logged.

    """

    action: AuditAction
    actor_id: uuid.UUID | None = None
    target_id: uuid.UUID | None = None
    payload: dict[str, str] = field(default_factory=dict[str, str])
