"""Status transitions of an outbox row: claim, outcome, deferral, sweep."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select, text, update

from ._backoff import next_attempt

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ._sources import OutboxSource

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)

STUCK_AFTER = timedelta(minutes=15)
POLL_LIMIT = 100
_SWEEP_LIMIT = 100


@dataclass(frozen=True, slots=True)
class PendingRow:
    """Snapshot of an outbox row, detached from its session.

    Attributes:
        source: OutboxSource - Table of the row.
        id: int - Id of the row: insertion order and the key of its outcome.
        event_name: str - Event name for the dispatcher.
        payload: dict[str, str] - Data of the event.
        attempt_count: int - Attempts made, the current one included.

    """

    source: OutboxSource
    id: int
    event_name: str
    payload: dict[str, str]
    attempt_count: int


async def claim(
    session: AsyncSession,
    source: OutboxSource,
    limit: int,
) -> list[PendingRow]:
    """Claim a batch of rows, `pending -> sending`, and commit the claim.

    Args:
        session: AsyncSession - Session; the function commits it.
        source: OutboxSource - Table to claim from.
        limit: int - Largest batch.

    Returns:
        list[PendingRow] - Claimed rows, oldest first.

    """
    model = source.model
    claimable = (
        select(model.id)
        .where(text(source.claimable))
        .order_by(model.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    result = await session.execute(
        update(model)
        .where(model.id.in_(claimable))
        .values(
            status=source.sending,
            claimed_at=func.now(),
            attempt_count=model.attempt_count + 1,
        )
        .returning(model.id, model.event_name, model.payload, model.attempt_count),
    )
    rows = [
        PendingRow(
            source=source,
            id=row_id,
            event_name=event_name,
            payload=payload,
            attempt_count=attempt_count,
        )
        for row_id, event_name, payload, attempt_count in result
    ]
    await session.commit()
    return sorted(rows, key=lambda row: row.id)


async def mark(
    session: AsyncSession,
    source: OutboxSource,
    row_id: int,
    status: str,
) -> None:
    """Move a row to a final status.

    Args:
        session: AsyncSession - Session of an open transaction.
        source: OutboxSource - Table of the row.
        row_id: int - The row.
        status: str - `source.sent` or `source.failed`.

    """
    values: dict[str, object] = {"status": status}
    if status == source.sent:
        values["published_at"] = func.now()
    _ = await session.execute(
        update(source.model).where(source.model.id == row_id).values(**values),
    )


async def defer(
    session: AsyncSession,
    source: OutboxSource,
    row_id: int,
    attempt_count: int,
) -> None:
    """Put a row off until its next attempt, or fail it once the attempts are spent.

    Args:
        session: AsyncSession - Session of an open transaction.
        source: OutboxSource - Table of the row.
        row_id: int - The row.
        attempt_count: int - Attempts made, the failed one included.

    """
    delay = next_attempt(attempt_count)
    if delay is None:
        _log.warning(
            "outbox_row_failed",
            table=source.name,
            row_id=row_id,
            attempts=attempt_count,
        )
        await mark(session, source, row_id, source.failed)
        return
    _ = await session.execute(
        update(source.model)
        .where(source.model.id == row_id)
        .values(
            status=source.pending,
            claimed_at=None,
            next_attempt_at=func.now() + delay,
        ),
    )


async def sweep(
    session: AsyncSession,
    source: OutboxSource,
    limit: int = _SWEEP_LIMIT,
) -> int:
    """Release rows whose worker died before marking their outcome.

    Args:
        session: AsyncSession - Session; the function commits it.
        source: OutboxSource - Table to sweep.
        limit: int - Largest number of rows per pass.

    Returns:
        int - Rows released (some of them failed rather than retried).

    """
    model = source.model
    stuck = await session.execute(
        select(model.id, model.attempt_count)
        .where(
            model.status == source.sending,
            model.claimed_at < func.now() - STUCK_AFTER,
        )
        .order_by(model.id)
        .limit(limit)
        .with_for_update(skip_locked=True),
    )
    rows = stuck.all()
    for row_id, attempt_count in rows:
        await defer(session, source, row_id, attempt_count)
    await session.commit()
    if rows:
        _log.warning(
            "outbox_rows_released",
            table=source.name,
            row_ids=[row_id for row_id, _ in rows],
        )
    return len(rows)
