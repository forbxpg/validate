"""Implementations of ``AuditLog`` and ``AuditQuery`` over ``AsyncSession``."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from sqlalchemy import func, insert, select

from ._port import AuditLog
from ._query import AuditPage, AuditQuery, AuditRecord
from ._table import AUDIT_LOG_TABLE

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from sqlalchemy import ColumnElement, Select
    from sqlalchemy.ext.asyncio import AsyncSession

    from ._entry import AuditEntry

    _LogRow = tuple[
        int,
        datetime,
        uuid.UUID | None,
        str,
        uuid.UUID | None,
        dict[str, str],
    ]


class SqlAlchemyAuditLog(AuditLog):
    """Audit log over the SQLAlchemy session."""

    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def record(self, entry: AuditEntry) -> None:
        """Record an event in the current transaction.

        Args:
            entry: AuditEntry - Event.

        """
        _ = await self._session.execute(
            insert(AUDIT_LOG_TABLE).values(
                actor_id=entry.actor_id,
                action=str(entry.action),
                target_id=entry.target_id,
                payload=entry.payload,
            ),
        )


class SqlAlchemyAuditQuery(AuditQuery):
    """Reading the audit log over the SQLAlchemy session."""

    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def search(
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
        conditions: list[ColumnElement[bool]] = []
        if actor_id is not None:
            conditions.append(AUDIT_LOG_TABLE.c.actor_id == actor_id)
        if target_id is not None:
            conditions.append(AUDIT_LOG_TABLE.c.target_id == target_id)
        if occurred_from is not None:
            conditions.append(AUDIT_LOG_TABLE.c.occurred_at >= occurred_from)
        if occurred_to is not None:
            conditions.append(AUDIT_LOG_TABLE.c.occurred_at < occurred_to)

        counting: Select[int] = select(func.count()).select_from(AUDIT_LOG_TABLE)
        total = (await self._session.execute(counting.where(*conditions))).scalar_one()

        rows = await self._session.execute(
            select(AUDIT_LOG_TABLE)
            .where(*conditions)
            .order_by(AUDIT_LOG_TABLE.c.id.desc())
            .limit(limit)
            .offset(offset),
        )
        typed_rows = cast("list[_LogRow]", [tuple(row) for row in rows])
        records = [
            AuditRecord(
                id=record_id,
                occurred_at=occurred_at,
                action=action,
                actor_id=actor_id,
                target_id=target_id,
                payload=payload,
            )
            for record_id, occurred_at, actor_id, action, target_id, payload in (
                typed_rows
            )
        ]
        return AuditPage(records=records, total=total)
