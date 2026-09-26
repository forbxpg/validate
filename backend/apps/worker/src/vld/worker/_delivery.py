"""Sending one letter: its own scope, both halves of the handler, one transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from vld.auth.application import (
    EmailPermanentlyUndeliverableError,
    UnknownRegisteredUserError,
    UnknownResetTargetError,
)
from vld.auth.domain import DomainEvent
from vld.core.database import UnitOfWork

from ._handlers import handler_type
from ._metrics import LETTER_SECONDS, LETTERS

if TYPE_CHECKING:
    from dishka import AsyncContainer

    from ._handlers import EventHandler

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)

_PERMANENT: tuple[type[Exception], ...] = (
    UnknownRegisteredUserError,
    UnknownResetTargetError,
    EmailPermanentlyUndeliverableError,
)


async def send_letter(
    handler: EventHandler,
    event: DomainEvent,
    delivery_id: int,
    uow: UnitOfWork,
) -> None:
    """Run both halves of a handler: preparation in a transaction, the letter outside.

    Args:
        handler: EventHandler - Handler of the event.
        event: DomainEvent - Event from the outbox row.
        delivery_id: int - Id of the row.
        uow: UnitOfWork - Boundary of the preparation.

    """
    async with uow:
        recipient, content = await handler.prepare(event, delivery_id)
        await uow.commit()
    await handler.deliver(recipient, content)


async def send_email(
    container: AsyncContainer,
    event_name: str,
    delivery_id: int,
    payload: dict[str, str],
) -> None:
    """Send the letter of a published message; a transient failure is raised for retry.

    Args:
        container: AsyncContainer - Root container.
        event_name: str - Event name from the outbox row.
        delivery_id: int - Id of the row.
        payload: dict[str, str] - Data of the event.

    """
    handler_cls = handler_type(event_name)
    if handler_cls is None:
        _log.warning(
            "email_task_unknown_event",
            event_name=event_name,
            delivery_id=delivery_id,
        )
        LETTERS.labels(event=event_name, outcome="dropped").inc()
        return
    async with container() as scope:
        # The unit of work and the stores of the handler share the scope session.
        uow = await scope.get(UnitOfWork)
        handler = await scope.get(handler_cls)
        try:
            with LETTER_SECONDS.labels(event=event_name).time():
                await send_letter(
                    handler,
                    DomainEvent(event_name, payload),
                    delivery_id,
                    uow,
                )
        except _PERMANENT as exc:
            LETTERS.labels(event=event_name, outcome="dropped").inc()
            _log.warning(
                "email_task_dropped",
                event_name=event_name,
                delivery_id=delivery_id,
                reason=type(exc).__name__,
            )
        except Exception:
            LETTERS.labels(event=event_name, outcome="failed").inc()
            raise
        else:
            LETTERS.labels(event=event_name, outcome="sent").inc()
