"""The delay before the next attempt to publish a row."""

from __future__ import annotations

from datetime import timedelta

from vld.worker._backoff import MAX_ATTEMPTS, next_attempt


def test_the_delay_doubles_from_ten_seconds() -> None:
    """The first retry waits ten seconds, each next one twice as long."""
    assert next_attempt(0) == timedelta(seconds=10)
    assert next_attempt(1) == timedelta(seconds=10)
    assert next_attempt(2) == timedelta(seconds=20)
    assert next_attempt(3) == timedelta(seconds=40)


def test_the_delay_is_capped_at_thirty_minutes() -> None:
    """The delay never grows past half an hour."""
    assert next_attempt(MAX_ATTEMPTS - 1) == timedelta(minutes=30)


def test_the_whole_retry_window_is_4350_seconds() -> None:
    """The sum of the delays is an operational number; then the row fails."""
    total = sum(
        (delay for n in range(1, MAX_ATTEMPTS) if (delay := next_attempt(n))),
        timedelta(),
    )

    assert total == timedelta(seconds=4350)
    assert next_attempt(MAX_ATTEMPTS) is None
