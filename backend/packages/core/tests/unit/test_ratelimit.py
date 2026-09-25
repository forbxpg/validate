"""Rate limiter decisions, with Redis replaced by in-memory doubles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from redis.exceptions import RedisError

from vld.core.ratelimit import (
    RateLimiter,
    RateLimiterUnavailableError,
    RateLimitExceededError,
    RedisScript,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class _CountingRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def register_script(self, script: str) -> RedisScript:
        del script

        async def _call(
            keys: Sequence[str] | None = None,
            args: Sequence[int] | None = None,
        ) -> list[int]:
            assert keys is not None
            assert args is not None
            self.counts[keys[0]] = self.counts.get(keys[0], 0) + 1
            return [self.counts[keys[0]], args[0]]

        return _call

    async def delete(self, *names: str) -> int:
        return sum(self.counts.pop(name, None) is not None for name in names)


class _DeadRedis:
    def register_script(self, script: str) -> RedisScript:
        del script

        async def _call(
            keys: Sequence[str] | None = None,
            args: Sequence[int] | None = None,
        ) -> list[int]:
            del keys, args
            msg = "connection refused"
            raise RedisError(msg)

        return _call

    async def delete(self, *names: str) -> int:
        del names
        msg = "connection refused"
        raise RedisError(msg)


async def test_attempts_up_to_the_limit_pass() -> None:
    """The limit counts allowed attempts, not the first refused one."""
    limiter = RateLimiter(_CountingRedis())

    for _ in range(3):
        await limiter.hit("k", limit=3, window_ms=60_000)


async def test_an_attempt_over_the_limit_is_refused_until_the_window_ends() -> None:
    """`Retry-After` is the rest of the window in seconds."""
    limiter = RateLimiter(_CountingRedis())
    await limiter.hit("k", limit=1, window_ms=60_000)

    with pytest.raises(RateLimitExceededError) as caught:
        await limiter.hit("k", limit=1, window_ms=60_000)

    assert caught.value.retry_after == 60
    assert not isinstance(caught.value, RateLimiterUnavailableError)


async def test_buckets_are_counted_apart() -> None:
    """One client exhausting its bucket does not block another."""
    limiter = RateLimiter(_CountingRedis())

    await limiter.hit("a", limit=1, window_ms=60_000)
    await limiter.hit("b", limit=1, window_ms=60_000)


async def test_the_limiter_fails_closed_when_redis_is_down() -> None:
    """Without its storage the limiter refuses rather than letting everyone in."""
    limiter = RateLimiter(_DeadRedis())

    with pytest.raises(RateLimiterUnavailableError):
        await limiter.hit("k", limit=100, window_ms=60_000)


async def test_reset_empties_the_bucket() -> None:
    """A successful login clears the failed attempts of that client."""
    redis = _CountingRedis()
    limiter = RateLimiter(redis)
    await limiter.hit("k", limit=1, window_ms=60_000)

    await limiter.reset("k")

    assert "k" not in redis.counts
    await limiter.hit("k", limit=1, window_ms=60_000)


async def test_reset_stays_quiet_when_redis_is_down() -> None:
    """A failed reset must not turn a successful login into an error."""
    await RateLimiter(_DeadRedis()).reset("k")
