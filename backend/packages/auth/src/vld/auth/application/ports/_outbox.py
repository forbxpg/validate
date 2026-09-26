"""Port of the transactional outbox."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from vld.auth.domain import DomainEvent


class Outbox(Protocol):
    """Writes domain events in the same transaction as the business data."""

    async def add(self, events: Sequence[DomainEvent]) -> None:
        """Add events to the outbox.

        Args:
            events: Sequence[DomainEvent] - Events taken from an aggregate.

        """
        ...
