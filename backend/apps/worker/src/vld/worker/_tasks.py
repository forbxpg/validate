"""The send task: its registration in the broker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._delivery import send_email

if TYPE_CHECKING:
    from dishka import AsyncContainer
    from taskiq import AsyncBroker

    from ._publish import EmailPublisher

SEND_EMAIL_TASK = "outbox.send_email"


def register(broker: AsyncBroker, container: AsyncContainer) -> EmailPublisher:
    """Register the send task and hand its publisher to the relay.

    Args:
        broker: AsyncBroker - Broker the task lives in.
        container: AsyncContainer - Root container.

    Returns:
        EmailPublisher - Publishes the task; the relay calls it for every row.

    """

    async def send_outbox_email(
        event_name: str,
        delivery_id: int,
        payload: dict[str, str],
    ) -> None:
        """Send the letter of an outbox row.

        Args:
            event_name: str - Event name from the row.
            delivery_id: int - Id of the row.
            payload: dict[str, str] - Data of the event.

        """
        await send_email(container, event_name, delivery_id, payload)

    return broker.register_task(
        send_outbox_email,
        SEND_EMAIL_TASK,
        retry_on_error=True,
    ).kiq
