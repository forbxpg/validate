"""Writing the outbox in the unit-of-work session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.infrastructure.models import OutboxModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from vld.auth.domain import DomainEvent


class SqlAlchemyOutbox:
    """Writes domain events into `auth.outbox`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, events: Sequence[DomainEvent]) -> None:
        """Write events as pending outbox rows.

        Args:
            events: Sequence[DomainEvent] - Events taken from an aggregate.

        """
        self._session.add_all(
            OutboxModel(event_name=event.name, payload=event.payload)
            for event in events
        )
        await self._session.flush()
