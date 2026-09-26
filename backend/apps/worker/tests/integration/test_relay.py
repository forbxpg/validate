"""Publishing outbox rows against a live PostgreSQL: pending to sent, poison to failed."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from vld.auth.domain import USER_REGISTERED_EVENT
from vld.core.database import SqlAlchemyUnitOfWork
from vld.worker._backoff import MAX_ATTEMPTS
from vld.worker._publish import publish_row
from vld.worker._rows import PendingRow, defer
from vld.worker._sources import (
    AUTH_OUTBOX,
    SOURCES,
    OutboxSource,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

# From the constants of the domains: the handler map reads the same.
_KNOWN_EVENT: dict[str, str] = {
    AUTH_OUTBOX.name: USER_REGISTERED_EVENT,
}

# The real list of the relay.
_SOURCES = SOURCES

# Table names as ids, to see which one failed.
_SOURCE_IDS = [source.name for source in _SOURCES]


class _RecordingPublisher:
    """A publisher that collects messages instead of reaching RabbitMQ."""

    def __init__(self) -> None:
        self.published: list[tuple[str, int, dict[str, str]]] = []

    async def __call__(
        self,
        event_name: str,
        delivery_id: int,
        payload: dict[str, str],
    ) -> object:
        self.published.append((event_name, delivery_id, payload))
        return None


def _payload() -> dict[str, str]:
    return {"user_id": str(uuid.uuid4())}


async def _insert_pending(
    engine: AsyncEngine,
    source: OutboxSource,
    event_name: str,
) -> tuple[int, dict[str, str]]:
    payload = _payload()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = source.model(event_name=event_name, payload=payload)
        session.add(row)
        await session.commit()
        return row.id, payload


async def _status(engine: AsyncEngine, source: OutboxSource, row_id: int) -> str:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(source.model.status).where(source.model.id == row_id),
        )
        return result.scalar_one()


async def _pending_ids(engine: AsyncEngine, source: OutboxSource) -> set[int]:
    # Reads instead of claiming: a claim would move rows of other tests.
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(source.model.id).where(source.model.status == source.pending),
        )
        return set(result.scalars())


async def _cleanup(engine: AsyncEngine, source: OutboxSource, ids: list[int]) -> None:
    async with AsyncSession(engine) as session:
        _ = await session.execute(
            delete(source.model).where(source.model.id.in_(ids)),
        )
        await session.commit()


def _row(
    source: OutboxSource,
    row_id: int,
    event_name: str,
    payload: dict[str, str],
) -> PendingRow:
    return PendingRow(
        source=source,
        id=row_id,
        event_name=event_name,
        payload=payload,
        attempt_count=1,
    )


@pytest.mark.parametrize("source", _SOURCES, ids=_SOURCE_IDS)
async def test_published_row_is_sent_and_gone_from_the_pending_set(
    db_engine: AsyncEngine,
    source: OutboxSource,
) -> None:
    """Pending becomes sent, the task is published, the next poll misses the row."""
    event_name = _KNOWN_EVENT[source.name]
    row_id, payload = await _insert_pending(db_engine, source, event_name)
    publisher = _RecordingPublisher()
    try:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            await publish_row(
                _row(source, row_id, event_name, payload),
                publisher,
                session,
                SqlAlchemyUnitOfWork(session),
            )

        assert publisher.published == [(event_name, row_id, payload)]
        assert await _status(db_engine, source, row_id) == source.sent

        async with AsyncSession(db_engine) as session:
            published = await session.execute(
                select(source.model.published_at).where(source.model.id == row_id),
            )
            assert published.scalar_one() is not None

        assert row_id not in await _pending_ids(db_engine, source)
    finally:
        await _cleanup(db_engine, source, [row_id])


@pytest.mark.parametrize("source", _SOURCES, ids=_SOURCE_IDS)
async def test_the_row_is_marked_sent_only_after_the_task_is_published(
    db_engine: AsyncEngine,
    source: OutboxSource,
) -> None:
    """While the task is published the row is still `sending`."""
    event_name = _KNOWN_EVENT[source.name]
    row_id, payload = await _insert_pending(db_engine, source, event_name)
    seen: list[str] = []

    async def _watching_publisher(
        published_event: str,
        delivery_id: int,
        published_payload: dict[str, str],
    ) -> object:
        del published_event, delivery_id, published_payload
        seen.append(await _status(db_engine, source, row_id))
        return None

    try:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            await publish_row(
                _row(source, row_id, event_name, payload),
                _watching_publisher,
                session,
                SqlAlchemyUnitOfWork(session),
            )

        assert len(seen) == 1, "the task must be published exactly once"
        assert seen[0] != source.sent, "the row must not be marked yet"
        assert await _status(db_engine, source, row_id) == source.sent
    finally:
        await _cleanup(db_engine, source, [row_id])


@pytest.mark.parametrize("source", _SOURCES, ids=_SOURCE_IDS)
async def test_unknown_event_is_failed_and_never_published(
    db_engine: AsyncEngine,
    source: OutboxSource,
) -> None:
    """Poison fails and nothing goes to the queue."""
    poison_event = "test.never_registered"
    poison_id, poison_payload = await _insert_pending(db_engine, source, poison_event)
    publisher = _RecordingPublisher()
    try:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            await publish_row(
                _row(source, poison_id, poison_event, poison_payload),
                publisher,
                session,
                SqlAlchemyUnitOfWork(session),
            )

        assert await _status(db_engine, source, poison_id) == source.failed
        assert publisher.published == []
        assert poison_id not in await _pending_ids(db_engine, source)
    finally:
        await _cleanup(db_engine, source, [poison_id])


@pytest.mark.parametrize("source", _SOURCES, ids=_SOURCE_IDS)
async def test_exhausted_row_goes_failed_with_a_warning(
    db_engine: AsyncEngine,
    source: OutboxSource,
) -> None:
    """Out of attempts, the row fails and the log says so."""
    row_id, _payload_unused = await _insert_pending(db_engine, source, "test.exhausted")

    try:
        with capture_logs() as logs:
            async with AsyncSession(db_engine) as session:
                await defer(session, source, row_id, MAX_ATTEMPTS)
                await session.commit()

        assert await _status(db_engine, source, row_id) == source.failed
        assert {
            "event": "outbox_row_failed",
            "table": source.name,
            "row_id": row_id,
            "attempts": MAX_ATTEMPTS,
            "log_level": "warning",
        } in logs, "spent attempts must be heard, with the table name"
    finally:
        await _cleanup(db_engine, source, [row_id])
