"""Audit log query port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """One read record of the audit log.

    Attributes:
        id: int - Record number (bigint identity).
        occurred_at: datetime - When it happened.
        action: str - What happened.
        actor_id: uuid.UUID | None - Who did it.
        target_id: uuid.UUID | None - Over whose account.
        payload: dict[str, str] - Useful record payload.

    """

    id: int
    occurred_at: datetime
    action: str
    actor_id: uuid.UUID | None
    target_id: uuid.UUID | None
    payload: dict[str, str]


@dataclass(frozen=True, slots=True)
class AuditPage:
    """One page of the audit log.

    Attributes:
        records: list[AuditRecord] - Records of the page, new ones first.
        total: int - How many records match the filter altogether, without the page.

    """

    records: list[AuditRecord]
    total: int


class AuditQuery(ABC):
    """Port for reading audit log."""

    @abstractmethod
    async def search(  # ruff: ignore[too-many-arguments] -- filters and page, all named
        self,
        *,
        actor_id: uuid.UUID | None,
        target_id: uuid.UUID | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        limit: int,
        offset: int,
    ) -> AuditPage:
        """Select a page of records by filters.

        Args:
            actor_id: uuid.UUID | None - Actor or None (any).
            target_id: uuid.UUID | None - Object or None (any).
            occurred_from: datetime | None - Lower bound, inclusive.
            occurred_to: datetime | None - Upper bound, exclusive.
            limit: int - Page size, strictly positive.
            offset: int - How many records to skip, non-negative.

        Returns:
            AuditPage - Page and total number of matching records.

        """
