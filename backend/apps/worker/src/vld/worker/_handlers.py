"""Handlers of outbox events: their contract and the map from event names."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from vld.auth.application import SendPasswordResetEmail, SendVerificationEmail
from vld.auth.domain import PASSWORD_RESET_REQUESTED_EVENT, USER_REGISTERED_EVENT

if TYPE_CHECKING:
    from vld.auth.domain import DomainEvent


class EventHandler(Protocol):
    """What the send task resolves and calls for one event."""

    async def prepare(self, event: DomainEvent, delivery_id: int) -> tuple[str, str]:
        """Store what the side effect needs and return its input.

        Args:
            event: DomainEvent - Event from the outbox row.
            delivery_id: int - Id of the row.

        Returns:
            tuple[str, str] - Recipient and what `deliver` needs.

        """
        ...

    async def deliver(self, recipient: str, content: str, /) -> None:
        """Perform the side effect outside the transaction.

        Args:
            recipient: str - Recipient.
            content: str - Second item of the pair from `prepare`.

        """
        ...


# An event missing here is poison: the relay marks its row failed.
HANDLERS: dict[str, type[EventHandler]] = {
    USER_REGISTERED_EVENT: SendVerificationEmail,
    PASSWORD_RESET_REQUESTED_EVENT: SendPasswordResetEmail,
}


def handler_type(event_name: str) -> type[EventHandler] | None:
    """Find the handler of an event.

    Args:
        event_name: str - Event name from the outbox row.

    Returns:
        type[EventHandler] | None - Handler type to resolve, or None for an event
            nobody handles.

    """
    return HANDLERS.get(event_name)
