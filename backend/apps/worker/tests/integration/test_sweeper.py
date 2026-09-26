"""Releasing rows whose worker died before marking the outcome."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete, func, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from vld.auth.infrastructure.models import OutboxModel, OutboxStatus
from vld.worker._backoff import MAX_ATTEMPTS
from vld.worker._rows import STUCK_AFTER, sweep
from vld.worker._sources import AUTH_OUTBOX

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

# Twice the threshold, so passing time cannot redden the test.
_LONG_AGO = STUCK_AFTER * 2

# The value only decides how fast the test reddens without SKIP LOCKED.
_LOCK_TIMEOUT = "1s"


async def _seed(
    engine: AsyncEngine,
    *,
    status: OutboxStatus,
    claimed_ago: timedelta,
    attempt_count: int = 1,
) -> int:
    """Insert a row and bring it to the state under test."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = OutboxModel(event_name="test.sweep", payload={})
        session.add(row)
        await session.commit()
        _ = await session.execute(
            update(OutboxModel)
            .where(OutboxModel.id == row.id)
            .values(
                status=status,
                claimed_at=func.now() - claimed_ago,
                attempt_count=attempt_count,
            ),
        )
        await session.commit()
        return row.id


async def _read(engine: AsyncEngine, row_id: int) -> OutboxModel:
    """Read the row in a session of its own."""
    async with AsyncSession(engine) as session:
        return await session.get_one(OutboxModel, row_id, populate_existing=True)


async def _drop(engine: AsyncEngine, row_id: int) -> None:
    """Remove the row the test inserted."""
    async with AsyncSession(engine) as session:
        _ = await session.execute(delete(OutboxModel).where(OutboxModel.id == row_id))
        await session.commit()


async def _sweep(engine: AsyncEngine) -> int:
    """Run the sweep in a session of its own."""
    async with AsyncSession(engine) as session:
        return await sweep(session, AUTH_OUTBOX)


async def _sweep_impatiently(engine: AsyncEngine) -> int:
    """Run the sweep in a session that may not wait for locks."""
    async with AsyncSession(engine) as session:
        _ = await session.execute(text(f"set local lock_timeout = '{_LOCK_TIMEOUT}'"))
        return await sweep(session, AUTH_OUTBOX)


async def test_stuck_row_returns_to_the_queue(db_engine: AsyncEngine) -> None:
    """A row stuck in `sending` goes back to the queue."""
    row_id = await _seed(db_engine, status=OutboxStatus.SENDING, claimed_ago=_LONG_AGO)
    try:
        assert await _sweep(db_engine) >= 1

        row = await _read(db_engine, row_id)
        assert row.status is OutboxStatus.PENDING
        assert row.claimed_at is None
        assert row.attempt_count == 1
        assert row.next_attempt_at is not None
    finally:
        await _drop(db_engine, row_id)


async def test_freshly_claimed_row_is_left_alone(db_engine: AsyncEngine) -> None:
    """A freshly claimed row is not taken from a live worker."""
    row_id = await _seed(
        db_engine,
        status=OutboxStatus.SENDING,
        claimed_ago=timedelta(0),
    )
    try:
        _ = await _sweep(db_engine)

        row = await _read(db_engine, row_id)
        assert row.status is OutboxStatus.SENDING
        assert row.claimed_at is not None
    finally:
        await _drop(db_engine, row_id)


async def test_sweeper_does_not_overwrite_an_outcome_being_committed(
    db_engine: AsyncEngine,
) -> None:
    """The sweep does not overwrite a row being marked `sent` right now."""
    row_id = await _seed(db_engine, status=OutboxStatus.SENDING, claimed_ago=_LONG_AGO)
    try:
        async with AsyncSession(db_engine) as marker:
            # A mark not yet committed, as between the delivery and the commit.
            _ = await marker.execute(
                update(OutboxModel)
                .where(OutboxModel.id == row_id)
                .values(status=OutboxStatus.SENT),
            )
            _ = await _sweep_impatiently(db_engine)
            await marker.commit()

        assert (await _read(db_engine, row_id)).status is OutboxStatus.SENT
    finally:
        await _drop(db_engine, row_id)


async def test_failed_row_with_a_stale_claim_is_not_resurrected(
    db_engine: AsyncEngine,
) -> None:
    """A failed row does not come back to the queue."""
    row_id = await _seed(
        db_engine,
        status=OutboxStatus.FAILED,
        claimed_ago=_LONG_AGO,
        attempt_count=3,
    )
    try:
        _ = await _sweep(db_engine)
        assert (await _read(db_engine, row_id)).status is OutboxStatus.FAILED
    finally:
        await _drop(db_engine, row_id)


async def test_stuck_row_out_of_attempts_goes_failed(db_engine: AsyncEngine) -> None:
    """A stuck row out of attempts fails instead of going back."""
    row_id = await _seed(
        db_engine,
        status=OutboxStatus.SENDING,
        claimed_ago=_LONG_AGO,
        attempt_count=MAX_ATTEMPTS,
    )
    try:
        assert await _sweep(db_engine) >= 1
        assert (await _read(db_engine, row_id)).status is OutboxStatus.FAILED
    finally:
        await _drop(db_engine, row_id)


async def test_row_with_a_zero_attempt_count_does_not_crash_the_sweeper(
    db_engine: AsyncEngine,
) -> None:
    """A `sending` row with a zero count is deferred, not a crash of the sweep."""
    row_id = await _seed(
        db_engine,
        status=OutboxStatus.SENDING,
        claimed_ago=_LONG_AGO,
        attempt_count=0,
    )
    try:
        assert await _sweep(db_engine) >= 1
        assert (await _read(db_engine, row_id)).status is OutboxStatus.PENDING
    finally:
        await _drop(db_engine, row_id)
