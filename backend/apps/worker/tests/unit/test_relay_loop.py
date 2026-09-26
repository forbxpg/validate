"""The relay loop survives a transient database failure, not a lasting one."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from prometheus_client import REGISTRY

from vld.worker import _relay
from vld.worker._publish import publish
from vld.worker._relay import (
    # The ceiling is imported, not copied as a number.
    _MAX_CONSECUTIVE_FAILURES,
    run,
)
from vld.worker._rows import PendingRow
from vld.worker._sources import AUTH_OUTBOX, SOURCES

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from dishka import AsyncContainer

# OSError: a dropped database connection arrives like this.
_BLINK = "pgbouncer blinked"
# The script symbol for "this turn fails"; anything else passes.
_FAIL = "x"
# A failure to resolve a dependency: broken settings, not a blinking database.
_BROKEN = "dependency is not configured"
# A pass longer than the pause: only then does fixed delay differ from fixed rate.
_SLOW_SWEEP = 100.0
_SWEEP_EVERY = 10.0


class _StubScope:
    """A scope that hands out a dummy instead of a session."""

    async def get(self, dependency: type) -> object:
        del dependency
        return object()


class _StubContainer:
    """A container that hands out one scope: exactly what `run` calls."""

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[_StubScope]:
        yield _StubScope()


async def _deaf_publisher(
    event_name: str,
    delivery_id: int,
    payload: dict[str, str],
) -> object:
    """A publisher these tests never call."""
    del event_name, delivery_id, payload
    msg = "nothing is published in these tests"
    raise AssertionError(msg)


def _container() -> AsyncContainer:
    """Give the stub container in the type `run` expects."""
    return cast("AsyncContainer", cast("object", _StubContainer()))


class _ScriptedClaim:
    """A scripted claim: fails on the listed turns, then asks to stop."""

    stop: asyncio.Event
    script: list[str]
    error: type[BaseException]
    turns: int

    def __init__(
        self,
        stop: asyncio.Event,
        script: str,
        error: type[BaseException] = OSError,
    ) -> None:
        self.stop = stop
        self.script = list(script)
        self.error = error
        self.turns = 0

    async def __call__(
        self,
        session: object,
        source: object,
        limit: int,
    ) -> list[PendingRow]:
        del session, limit
        if source is not SOURCES[0]:
            return []
        self.turns += 1
        if not self.script:
            self.stop.set()
            return []
        if self.script.pop(0) == _FAIL:
            raise self.error(_BLINK)
        return []


async def _sweep_ok(session: object, source: object) -> int:
    """A sweep with nothing to release: in these tests the claim fails."""
    del session, source
    return 0


def _arm(
    monkeypatch: pytest.MonkeyPatch,
    stop: asyncio.Event,
    script: str = "",
    error: type[BaseException] = OSError,
) -> _ScriptedClaim:
    """Replace the row transitions with the script and return it."""
    claim = _ScriptedClaim(stop, script, error)
    monkeypatch.setattr(_relay, "claim", claim)
    monkeypatch.setattr(_relay, "sweep", _sweep_ok)
    return claim


async def _run(container: AsyncContainer, stop: asyncio.Event) -> None:
    """Turn the relay without pauses and without a second sweep."""
    await run(
        container,
        _deaf_publisher,
        stop,
        limit=1,
        interval=0.0,
        sweep_interval=1_000.0,
    )


async def test_transient_db_failure_does_not_kill_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A database failure is survived: the next turn passes."""
    stop = asyncio.Event()
    claim = _arm(monkeypatch, stop, _FAIL)

    await _run(_container(), stop)

    assert claim.turns == 2, "a next turn must follow the failure"
    assert stop.is_set(), "the loop must live until the stop flag"


async def test_sweep_failure_does_not_kill_the_loop_either(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken sweep degrades to "stuck rows stay", not to a dead loop."""
    stop = asyncio.Event()
    claim = _arm(monkeypatch, stop)
    calls = 0

    async def _sweep_always_broken(session: object, source: object) -> int:
        del session, source
        nonlocal calls
        calls += 1
        raise OSError(_BLINK)

    monkeypatch.setattr(_relay, "sweep", _sweep_always_broken)

    await _run(_container(), stop)

    assert calls == 1, "the sweep deadline must move on a failed pass too"
    assert claim.turns == 1, "delivery must go on the very next turn"
    assert stop.is_set(), "a broken sweep must not bring the loop down"


async def test_a_successful_turn_resets_the_failure_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counter counts failures in a row, not in total."""
    stop = asyncio.Event()
    claim = _arm(monkeypatch, stop, "x." * _MAX_CONSECUTIVE_FAILURES)

    await _run(_container(), stop)

    assert claim.turns == 2 * _MAX_CONSECUTIVE_FAILURES + 1
    assert stop.is_set(), "scattered failures must not add up to the ceiling"


async def test_the_loop_gives_up_after_the_ceiling_of_consecutive_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At the ceiling of failures in a row `run` raises."""
    stop = asyncio.Event()
    claim = _arm(monkeypatch, stop, _FAIL * _MAX_CONSECUTIVE_FAILURES)

    with pytest.raises(OSError, match=_BLINK):
        await _run(_container(), stop)

    assert claim.turns == _MAX_CONSECUTIVE_FAILURES
    assert not stop.is_set(), "the loop gave up by itself, not on a stop request"


async def test_a_slow_sweep_waits_the_interval_after_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sweep pause counts from the end of the pass, not its start."""
    stop = asyncio.Event()
    _ = _arm(monkeypatch, stop, "." * 4)
    clock = [0.0]
    calls = 0

    async def _sweep_slow(session: object, source: object) -> int:
        del session, source
        nonlocal calls
        calls += 1
        clock[0] += _SLOW_SWEEP
        return 0

    monkeypatch.setattr(_relay, "sweep", _sweep_slow)
    monkeypatch.setattr(
        _relay,
        "time",
        SimpleNamespace(monotonic=lambda: clock[0]),
    )

    await run(
        _container(),
        _deaf_publisher,
        stop,
        limit=1,
        interval=0.0,
        sweep_interval=_SWEEP_EVERY,
    )

    assert calls == len(SOURCES), (
        "a pass longer than the interval must not run back to back; "
        "one call per table is ONE pass"
    )


async def test_a_failed_turn_still_pauses(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed turn pays the same pause as a successful one."""
    stop = asyncio.Event()
    pause = 0.05
    _ = _arm(monkeypatch, stop, _FAIL)

    started = time.monotonic()
    await run(
        _container(),
        _deaf_publisher,
        stop,
        limit=1,
        interval=pause,
        sweep_interval=1_000.0,
    )
    elapsed = time.monotonic() - started

    assert elapsed >= pause, (
        "without a pause on failure the ceiling encodes no time budget"
    )


async def test_dependency_resolution_failure_reaches_the_loop() -> None:
    """A failure to resolve the row dependencies is raised, not swallowed."""

    class _BrokenScope:
        async def get(self, dependency: type) -> object:
            del dependency
            raise RuntimeError(_BROKEN)

    class _BrokenContainer:
        @asynccontextmanager
        async def __call__(self) -> AsyncGenerator[_BrokenScope]:
            yield _BrokenScope()

    container = cast("AsyncContainer", cast("object", _BrokenContainer()))
    row = PendingRow(
        source=AUTH_OUTBOX,
        id=1,
        event_name="auth.user_registered",
        payload={},
        attempt_count=1,
    )

    with pytest.raises(RuntimeError, match=_BROKEN):
        await publish(container, _deaf_publisher, row)


async def test_a_claimed_row_goes_to_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A claimed row reaches publication."""
    stop = asyncio.Event()
    row = PendingRow(
        source=AUTH_OUTBOX,
        id=7,
        event_name="auth.user_registered",
        payload={"user_id": "u"},
        attempt_count=1,
    )
    published: list[PendingRow] = []

    handed: list[PendingRow] = []

    async def _claim_one(
        session: object,
        source: object,
        limit: int,
    ) -> list[PendingRow]:
        del session, limit
        # The claim stops the loop, not the publisher: a mutant would hang the run.
        if source is AUTH_OUTBOX and not handed:
            handed.append(row)
            return [row]
        stop.set()
        return []

    async def _publish_recording(
        container: object,
        publish_task: object,
        claimed: PendingRow,
    ) -> None:
        del container, publish_task
        published.append(claimed)

    monkeypatch.setattr(_relay, "claim", _claim_one)
    monkeypatch.setattr(_relay, "sweep", _sweep_ok)
    monkeypatch.setattr(_relay, "publish", _publish_recording)

    await run(
        _container(),
        _deaf_publisher,
        stop,
        limit=1,
        interval=0.0,
        sweep_interval=1_000.0,
    )

    assert published == [row], "a claimed row must go to publication"


async def test_one_turn_touches_every_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """A turn visits every table, by claim and by sweep."""
    stop = asyncio.Event()
    claimed: list[object] = []
    swept: list[object] = []

    async def _claim_recording(
        session: object,
        source: object,
        limit: int,
    ) -> list[PendingRow]:
        del session, limit
        claimed.append(source)
        if len(claimed) >= len(SOURCES):
            stop.set()
        return []

    async def _sweep_recording(session: object, source: object) -> int:
        del session
        swept.append(source)
        return 0

    monkeypatch.setattr(_relay, "claim", _claim_recording)
    monkeypatch.setattr(_relay, "sweep", _sweep_recording)

    await run(
        _container(),
        _deaf_publisher,
        stop,
        limit=1,
        interval=0.0,
        sweep_interval=1_000.0,
    )

    assert claimed == list(SOURCES), "the claim must visit every table"
    assert swept == list(SOURCES), "the sweep must visit every table"


async def test_cancellation_passes_straight_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CancelledError` is not a failed turn and passes straight through."""
    stop = asyncio.Event()
    claim = _arm(monkeypatch, stop, _FAIL, error=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await _run(_container(), stop)

    assert claim.turns == 1, "a cancellation must leave on the very first turn"
    assert not stop.is_set()


async def test_claimed_and_swept_rows_are_counted_per_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prometheus sees how many rows each table hands to the relay."""
    rows = [
        PendingRow(
            source=AUTH_OUTBOX,
            id=n,
            event_name="auth.user_registered",
            payload={},
            attempt_count=1,
        )
        for n in (1, 2)
    ]

    async def _claim_two(
        session: object,
        source: object,
        limit: int,
    ) -> list[PendingRow]:
        del session, source, limit
        return rows

    async def _sweep_three(session: object, source: object) -> int:
        del session, source
        return 3

    monkeypatch.setattr(_relay, "claim", _claim_two)
    monkeypatch.setattr(_relay, "sweep", _sweep_three)
    labels = {"table": AUTH_OUTBOX.name}
    claimed = (
        REGISTRY.get_sample_value("vld_worker_outbox_claimed_total", labels) or 0.0
    )
    swept = REGISTRY.get_sample_value("vld_worker_outbox_swept_total", labels) or 0.0

    _ = await _relay._claim_batch(_container(), AUTH_OUTBOX, 10)
    _ = await _relay._sweep_stuck(_container(), AUTH_OUTBOX)

    assert (
        REGISTRY.get_sample_value("vld_worker_outbox_claimed_total", labels)
        == claimed + 2
    )
    assert (
        REGISTRY.get_sample_value("vld_worker_outbox_swept_total", labels) == swept + 3
    )
