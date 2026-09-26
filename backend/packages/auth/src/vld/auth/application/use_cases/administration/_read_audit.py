"""Reading the audit log."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from vld.core.audit import AuditPage, AuditQuery


class ReadAudit:
    """Return a page of the audit log by filters."""

    def __init__(self, audit: AuditQuery) -> None:
        self._audit: AuditQuery = audit

    async def __call__(  # ruff: ignore[too-many-arguments] -- filters and a page, all named
        self,
        *,
        actor_id: uuid.UUID | None,
        target_id: uuid.UUID | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        limit: int,
        offset: int,
    ) -> AuditPage:
        """Select a page of the log.

        Args:
            actor_id: uuid.UUID | None - Actor, or None for any.
            target_id: uuid.UUID | None - Target, or None for any.
            occurred_from: datetime | None - Lower bound, inclusive.
            occurred_to: datetime | None - Upper bound, exclusive.
            limit: int - Page size; the HTTP layer bounds it.
            offset: int - Records to skip.

        Returns:
            AuditPage - The page and the number of matching records.

        """
        return await self._audit.search(
            actor_id=actor_id,
            target_id=target_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        )
