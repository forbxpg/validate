"""Limits of one process: rate, concurrency and the limits Crossref reports."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from crossref_support import FakeClock
from structlog.testing import capture_logs

from vld.crossref import LocalThrottle, RateLimits
from vld.crossref.throttle import _headers, parse_limits


async def test_the_rate_never_exceeds_the_limit_in_any_window() -> None:
    """Twenty-five entries at 10 per second take the time they must."""
    clock = FakeClock()
    throttle = LocalThrottle(
        RateLimits(10, timedelta(seconds=1), None),
        clock=clock,
        sleep=clock.sleep,
    )
    entries: list[float] = []

    for _ in range(25):
        async with throttle.slot():
            entries.append(clock())

    for start in entries:
        assert sum(1 for moment in entries if start <= moment < start + 1) <= 10
    assert entries[-1] - entries[0] >= 2.0


async def test_concurrency_never_exceeds_the_limit() -> None:
    """With three places, the fourth request waits for one to free."""
    throttle = LocalThrottle(RateLimits(1000, timedelta(seconds=1), 3))
    release = asyncio.Event()
    inside = 0
    most = 0

    async def request() -> None:
        nonlocal inside, most
        async with throttle.slot():
            inside += 1
            most = max(most, inside)
            await release.wait()
            inside -= 1

    tasks = [asyncio.create_task(request()) for _ in range(5)]
    await asyncio.sleep(0.01)
    assert inside == 3
    release.set()
    await asyncio.gather(*tasks)
    assert most == 3


async def test_observed_limits_apply_to_waiting_requests() -> None:
    """Growing the concurrency wakes the waiters at once."""
    throttle = LocalThrottle(RateLimits(1000, timedelta(seconds=1), 1))
    release = asyncio.Event()
    inside = 0

    async def request() -> None:
        nonlocal inside
        async with throttle.slot():
            inside += 1
            await release.wait()

    tasks = [asyncio.create_task(request()) for _ in range(3)]
    await asyncio.sleep(0.01)
    assert inside == 1
    await throttle.observe(RateLimits(1000, timedelta(seconds=1), 3))
    await asyncio.sleep(0.01)
    assert inside == 3
    assert throttle.limits.concurrency == 3
    release.set()
    await asyncio.gather(*tasks)


async def test_no_concurrency_limit_lets_everyone_in() -> None:
    """Plus has no concurrency limit."""
    throttle = LocalThrottle(RateLimits.PLUS)
    release = asyncio.Event()
    inside = 0

    async def request() -> None:
        nonlocal inside
        async with throttle.slot():
            inside += 1
            await release.wait()

    tasks = [asyncio.create_task(request()) for _ in range(20)]
    await asyncio.sleep(0.01)
    assert inside == 20
    release.set()
    await asyncio.gather(*tasks)


def test_the_pools_of_crossref() -> None:
    """The documented pools, checked on 2026-09-26."""
    assert (RateLimits.PUBLIC.requests, RateLimits.PUBLIC.concurrency) == (5, 1)
    assert (RateLimits.POLITE.requests, RateLimits.POLITE.concurrency) == (10, 3)
    assert (RateLimits.PLUS.requests, RateLimits.PLUS.concurrency) == (150, None)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        (
            {
                "x-rate-limit-limit": "10",
                "x-rate-limit-interval": "1s",
                "x-concurrency-limit": "3",
                "x-api-pool": "polite",
            },
            RateLimits(10, timedelta(seconds=1), 3, "polite"),
        ),
        (
            {"x-rate-limit-limit": "150", "x-rate-limit-interval": "500ms"},
            RateLimits(150, timedelta(milliseconds=500), None),
        ),
        (
            {
                "x-rate-limit-limit": "5",
                "x-rate-limit-interval": "2m",
                "x-concurrency-limit": "1",
            },
            RateLimits(5, timedelta(minutes=2), 1),
        ),
        ({}, None),
    ],
)
def test_limits_are_read_from_the_headers(
    headers: dict[str, str],
    expected: RateLimits | None,
) -> None:
    """Every documented header and interval unit is read."""
    assert parse_limits(headers) == expected


def test_malformed_limits_are_ignored_with_one_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A strange header is logged once, not on every response."""
    monkeypatch.setattr(_headers, "_warned", set[str]())
    headers = {"x-rate-limit-limit": "ten", "x-rate-limit-interval": "1s"}

    with capture_logs() as logs:
        assert parse_limits(headers) is None
        assert parse_limits(headers) is None

    assert [entry["event"] for entry in logs] == ["crossref_limits_unreadable"]
