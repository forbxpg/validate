"""Polling relay of the transactional outbox: claims rows, publishes tasks."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ._metrics import OUTBOX_CLAIMED, OUTBOX_SWEPT, RELAY_TURN_FAILURES
from ._publish import publish
from ._rows import POLL_LIMIT, claim, sweep
from ._sources import SOURCES

if TYPE_CHECKING:
    from dishka import AsyncContainer

    from ._publish import EmailPublisher
    from ._rows import PendingRow
    from ._sources import OutboxSource

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


_POLL_INTERVAL = 1.0
_SWEEP_INTERVAL = 60.0
_MAX_CONSECUTIVE_FAILURES = 10


async def _claim_batch(
    container: AsyncContainer,
    source: OutboxSource,
    limit: int,
) -> list[PendingRow]:
    """Claim a batch of one table in a short scope of its own.

    Args:
        container: AsyncContainer - Root container.
        source: OutboxSource - Table to claim from.
        limit: int - Largest batch.

    Returns:
        list[PendingRow] - Claimed rows.

    """
    async with container() as scope:
        rows = await claim(await scope.get(AsyncSession), source, limit)
    OUTBOX_CLAIMED.labels(table=source.name).inc(len(rows))
    return rows


async def _sweep_stuck(container: AsyncContainer, source: OutboxSource) -> int:
    """Release the abandoned rows of one table in a short scope of its own.

    Args:
        container: AsyncContainer - Root container.
        source: OutboxSource - Table to sweep.

    Returns:
        int - Rows released.

    """
    async with container() as scope:
        released = await sweep(await scope.get(AsyncSession), source)
    OUTBOX_SWEPT.labels(table=source.name).inc(released)
    return released


async def _publish_batches(
    container: AsyncContainer,
    publish_task: EmailPublisher,
    stop: asyncio.Event,
    limit: int,
) -> None:
    """Claim a batch of every table and publish each row.

    Args:
        container: AsyncContainer - Root container.
        publish_task: EmailPublisher - Publishes the send task.
        stop: asyncio.Event - Set on shutdown.
        limit: int - Largest batch per table.

    """
    for source in SOURCES:
        if stop.is_set():
            break
        for row in await _claim_batch(container, source, limit):
            if stop.is_set():
                break
            await publish(container, publish_task, row)


async def run(  # ruff: ignore[too-many-arguments] -- two dependencies, a flag and three paces
    container: AsyncContainer,
    publish_task: EmailPublisher,
    stop: asyncio.Event,
    *,
    limit: int = POLL_LIMIT,
    interval: float = _POLL_INTERVAL,
    sweep_interval: float = _SWEEP_INTERVAL,
) -> None:
    """Turn the relay until asked to stop.

    Args:
        container: AsyncContainer - Root container.
        publish_task: EmailPublisher - Publishes the send task.
        stop: asyncio.Event - Set on shutdown.
        limit: int - Largest batch per table.
        interval: float - Pause between turns, seconds.
        sweep_interval: float - Pause between sweeps, seconds.

    A turn failing `_MAX_CONSECUTIVE_FAILURES` times in a row is raised: the database
    is down for good, and falling is louder than staying quiet.

    """
    # Monotonic: a clock set back does not freeze the sweep.
    next_sweep = 0.0
    failures = 0
    while not stop.is_set():
        # One turn is one unit of failure; splitting it would split the counter.
        try:  # ruff: ignore[too-many-statements-in-try-clause]
            if time.monotonic() >= next_sweep:
                # In `finally`, or a failed sweep leaves the deadline in the past;
                # after the pass, or a slow sweep would shorten the pause.
                try:
                    await _sweep_all(container)
                finally:
                    next_sweep = time.monotonic() + sweep_interval
            await _publish_batches(container, publish_task, stop, limit)
        except Exception as exc:
            failures += 1
            RELAY_TURN_FAILURES.inc()
            if failures >= _MAX_CONSECUTIVE_FAILURES:
                _log.exception("outbox_relay_gave_up", failures=failures)
                raise
            _log.warning("outbox_relay_turn_failed", failures=failures, error=repr(exc))
        else:
            failures = 0
        with contextlib.suppress(TimeoutError):
            _ = await asyncio.wait_for(stop.wait(), timeout=interval)


async def _sweep_all(container: AsyncContainer) -> None:
    """Release the abandoned rows of every table.

    Args:
        container: AsyncContainer - Root container.

    """
    for source in SOURCES:
        _ = await _sweep_stuck(container, source)
