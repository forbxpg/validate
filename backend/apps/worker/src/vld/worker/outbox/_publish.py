"""Publishing one outbox row: its own scope, a task to the broker, the outcome."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from vld.core.database import UnitOfWork
from vld.worker.tasks import handler_type

from ._metrics import OUTBOX_DEFERRED, OUTBOX_FAILED, OUTBOX_PUBLISHED
from ._rows import defer, mark

if TYPE_CHECKING:
    from dishka import AsyncContainer

    from vld.worker.tasks import EmailPublisher

    from ._rows import PendingRow

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


async def publish_row(
    row: PendingRow,
    publish_task: EmailPublisher,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    """Publish the task of a row and mark the row published.

    Args:
        row: PendingRow - Claimed row, already `sending`.
        publish_task: EmailPublisher - Publishes the send task.
        session: AsyncSession - Session of the unit of work.
        uow: UnitOfWork - Boundary of the marking transaction.

    """
    if handler_type(row.event_name) is None:
        _log.warning(
            "outbox_unknown_event",
            table=row.source.name,
            row_id=row.id,
            event_name=row.event_name,
        )
        async with uow:
            await mark(session, row.source, row.id, row.source.failed)
            await uow.commit()
        OUTBOX_FAILED.labels(table=row.source.name).inc()
        return

    _ = await publish_task(row.event_name, row.id, row.payload)
    async with uow:
        await mark(session, row.source, row.id, row.source.sent)
        await uow.commit()
    OUTBOX_PUBLISHED.labels(table=row.source.name).inc()


async def publish(
    container: AsyncContainer,
    publish_task: EmailPublisher,
    row: PendingRow,
) -> None:
    """Publish one row in its own request scope, deferring it on failure.

    A failure to resolve the dependencies is shared by every row, so it is raised
    rather than burning the rows one by one.

    Args:
        container: AsyncContainer - Root container.
        publish_task: EmailPublisher - Publishes the send task.
        row: PendingRow - The row.

    """
    async with container() as scope:
        session = await scope.get(AsyncSession)
        uow = await scope.get(UnitOfWork)
        try:
            await publish_row(row, publish_task, session, uow)
        except Exception:  # ruff: ignore[blind-except] -- one row must not stop the relay
            _log.exception(
                "outbox_row_not_published",
                table=row.source.name,
                row_id=row.id,
                event_name=row.event_name,
            )
            try:
                async with uow:
                    await defer(session, row.source, row.id, row.attempt_count)
                    await uow.commit()
                OUTBOX_DEFERRED.labels(table=row.source.name).inc()
            except Exception:  # ruff: ignore[blind-except] -- the sweep releases it later
                _log.exception(
                    "outbox_row_left_claimed",
                    table=row.source.name,
                    row_id=row.id,
                )
