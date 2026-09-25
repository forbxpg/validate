"""The retry policy: transient errors get another call, the rest do not."""

from __future__ import annotations

import asyncio

import pytest

from vld.crossref.core import (
    CrossrefNotFoundError,
    CrossrefRateLimitError,
    CrossrefServerError,
    retry,
)


class _Flaky:
    def __init__(self, *errors: Exception) -> None:
        self.errors: list[Exception] = list(errors)
        self.calls: int = 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "found"


@pytest.fixture
def pauses(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the pauses instead of sleeping through them."""
    recorded: list[float] = []

    async def _sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _sleep)
    return recorded


async def test_a_transient_error_gets_another_call(pauses: list[float]) -> None:
    """A rate limit or a 5xx usually passes by the next call."""
    call = _Flaky(CrossrefRateLimitError())

    result = await retry(attempts=3, delay_seconds=2.0)(call)()

    assert result == "found"
    assert call.calls == 2
    assert pauses == [2.0]


async def test_the_last_error_keeps_its_type(pauses: list[float]) -> None:
    """A server error must not turn into a client error after the last attempt."""
    call = _Flaky(*(CrossrefServerError() for _ in range(3)))

    with pytest.raises(CrossrefServerError):
        _ = await retry(attempts=3)(call)()

    assert call.calls == 3
    assert len(pauses) == 2, "no pause after the last attempt"


async def test_a_permanent_error_is_not_repeated(pauses: list[float]) -> None:
    """Nothing is found the second time either: the error goes out at once."""
    call = _Flaky(CrossrefNotFoundError())

    with pytest.raises(CrossrefNotFoundError):
        _ = await retry(attempts=3)(call)()

    assert call.calls == 1
    assert pauses == []


def test_fewer_than_one_attempt_is_refused() -> None:
    """Zero attempts would never call the function at all."""
    with pytest.raises(ValueError, match="at least 1"):
        _ = retry(attempts=0)
