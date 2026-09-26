"""Delay before the next attempt to publish an outbox row."""

from __future__ import annotations

from datetime import timedelta

_BASE = timedelta(seconds=10)
_CAP = timedelta(minutes=30)
MAX_ATTEMPTS = 10


def next_attempt(attempt_count: int) -> timedelta | None:
    """Tell how long to wait before the next attempt.

    Args:
        attempt_count: int - Attempts made so far, the failed one included.

    Returns:
        timedelta | None - The delay, or None once the attempts are spent and the
            row goes to `failed`.

    """
    if attempt_count >= MAX_ATTEMPTS:
        return None
    return min(_BASE * (1 << max(attempt_count - 1, 0)), _CAP)
