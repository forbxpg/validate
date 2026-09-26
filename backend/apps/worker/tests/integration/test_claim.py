"""Claiming outbox rows against a live PostgreSQL."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from vld.auth.infrastructure.models import (
    CLAIMABLE_PREDICATE,
    OutboxModel,
    OutboxStatus,
)
from vld.worker.outbox._rows import POLL_LIMIT, claim
from vld.worker.outbox._sources import AUTH_OUTBOX

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

# An event of its own, so the rows are removed whole.
_BULK_EVENT = "test.claim.bulk"

# On an empty table the planner scans whatever the predicate; 500 rows are enough.
_BULK_ROWS = 500

_DEFER_ROW = """
    update auth.outbox set next_attempt_at = now() + interval '1 hour'
    where id = :id
"""

_FILL_TABLE = f"""
    insert into auth.outbox (event_name, payload, status, published_at)
    select :event, '{{}}'::jsonb, 'sent', now()
    from generate_series(1, {_BULK_ROWS})
"""  # ruff: ignore[hardcoded-sql-expression] -- a module constant

# The production claim limit: the test reads the plan of the same query.
_CLAIM_LIMIT = POLL_LIMIT

_CLAIM_PLAN = f"""
    explain select id from auth.outbox where {CLAIMABLE_PREDICATE}
    order by id limit {_CLAIM_LIMIT} for update skip locked
"""  # ruff: ignore[hardcoded-sql-expression] -- the model predicate


async def _seed(engine: AsyncEngine, count: int) -> list[int]:
    """Insert `count` pending rows and return their ids."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        rows = [
            OutboxModel(event_name="test.claim", payload={"n": str(n)})
            for n in range(count)
        ]
        session.add_all(rows)
        await session.commit()
        return [row.id for row in rows]


async def _drop(engine: AsyncEngine, ids: list[int]) -> None:
    """Remove the rows the test inserted."""
    async with AsyncSession(engine) as session:
        _ = await session.execute(delete(OutboxModel).where(OutboxModel.id.in_(ids)))
        await session.commit()


async def test_two_workers_never_claim_the_same_row(db_engine: AsyncEngine) -> None:
    """Two concurrent workers share the rows, never both taking one."""
    ids = await _seed(db_engine, 6)
    try:
        async with (
            AsyncSession(db_engine) as first,
            AsyncSession(db_engine) as second,
        ):
            got_first, got_second = await asyncio.gather(
                claim(first, AUTH_OUTBOX, 3),
                claim(second, AUTH_OUTBOX, 3),
            )
        taken_first = {row.id for row in got_first}
        taken_second = {row.id for row in got_second}
        assert not (taken_first & taken_second), "a row went to two workers"
        assert len(taken_first | taken_second) == 6
    finally:
        await _drop(db_engine, ids)


async def test_claim_skips_locked_rows_instead_of_waiting_for_them(
    db_engine: AsyncEngine,
) -> None:
    """Rows locked by another transaction are skipped, not waited for."""
    ids = await _seed(db_engine, 4)
    locked, free = ids[:2], ids[2:]
    try:
        async with AsyncSession(db_engine) as holder:
            _ = await holder.execute(
                select(OutboxModel.id)
                .where(OutboxModel.id.in_(locked))
                .with_for_update(),
            )
            async with AsyncSession(db_engine) as worker:
                claimed = await asyncio.wait_for(
                    claim(worker, AUTH_OUTBOX, 10),
                    timeout=5,
                )
            await holder.rollback()

        assert [row.id for row in claimed] == free
    finally:
        await _drop(db_engine, ids)


async def test_claim_moves_rows_to_sending_and_counts_the_attempt(
    db_engine: AsyncEngine,
) -> None:
    """A claim marks `sending`, sets `claimed_at` and counts the attempt."""
    ids = await _seed(db_engine, 1)
    try:
        async with AsyncSession(db_engine) as session:
            claimed = await claim(session, AUTH_OUTBOX, 10)
        assert [row.id for row in claimed] == ids
        assert [row.attempt_count for row in claimed] == [1]

        async with AsyncSession(db_engine) as session:
            row = (
                await session.execute(
                    select(OutboxModel).where(OutboxModel.id == ids[0]),
                )
            ).scalar_one()
            assert row.status is OutboxStatus.SENDING
            assert row.claimed_at is not None
            assert row.attempt_count == 1
    finally:
        await _drop(db_engine, ids)


async def test_deferred_row_is_not_claimed_before_its_time(
    db_engine: AsyncEngine,
) -> None:
    """A row whose `next_attempt_at` is ahead is not taken."""
    ids = await _seed(db_engine, 1)
    try:
        async with AsyncSession(db_engine) as session:
            _ = await session.execute(text(_DEFER_ROW), {"id": ids[0]})
            await session.commit()

        async with AsyncSession(db_engine) as session:
            assert await claim(session, AUTH_OUTBOX, 10) == []
    finally:
        await _drop(db_engine, ids)


async def test_claim_uses_the_partial_index(db_engine: AsyncEngine) -> None:
    """The claim uses the index, not a scan of the table."""
    ids = await _seed(db_engine, 3)
    try:
        async with AsyncSession(db_engine) as session:
            _ = await session.execute(text(_FILL_TABLE), {"event": _BULK_EVENT})
            await session.commit()
            # Without analyze the planner works from stale statistics.
            _ = await session.execute(text("analyze auth.outbox"))

            plan = await session.execute(text(_CLAIM_PLAN))
            # `text()` carries no types; explain returns one text column.
            text_plan = "\n".join(cast("list[str]", plan.scalars().all()))
        assert "ix_outbox_pending" in text_plan, text_plan
    finally:
        async with AsyncSession(db_engine) as session:
            _ = await session.execute(
                delete(OutboxModel).where(OutboxModel.event_name == _BULK_EVENT),
            )
            await session.commit()
        await _drop(db_engine, ids)
