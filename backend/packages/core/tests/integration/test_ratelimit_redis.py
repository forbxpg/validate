"""The Lua script of the rate limiter against a live Redis."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from vld.core.ratelimit import RateLimiter, RateLimitExceededError

if TYPE_CHECKING:
    from redis.asyncio import Redis

pytestmark = pytest.mark.integration


async def test_an_attempt_over_the_limit_is_refused(redis_client: Redis) -> None:
    """The script counts and compares in one round trip."""
    limiter = RateLimiter(redis_client)
    for _ in range(3):
        await limiter.hit("k", limit=3, window_ms=60_000)

    with pytest.raises(RateLimitExceededError):
        await limiter.hit("k", limit=3, window_ms=60_000)


async def test_the_first_attempt_sets_the_expiry(redis_client: Redis) -> None:
    """A bucket without a TTL would lock its client out forever."""
    await RateLimiter(redis_client).hit("k", limit=3, window_ms=60_000)

    ttl_ms = await redis_client.pttl("k")

    assert 0 < ttl_ms <= 60_000


async def test_the_window_is_fixed_not_sliding(redis_client: Redis) -> None:
    """A sliding window would never release a client that keeps retrying."""
    limiter = RateLimiter(redis_client)
    await limiter.hit("fixed", limit=10, window_ms=5_000)
    first_ttl = await redis_client.pttl("fixed")
    await asyncio.sleep(0.3)

    await limiter.hit("fixed", limit=10, window_ms=5_000)

    assert await redis_client.pttl("fixed") < first_ttl


async def test_reset_clears_the_bucket(redis_client: Redis) -> None:
    """After a reset the next attempt opens a new window."""
    limiter = RateLimiter(redis_client)
    for _ in range(3):
        await limiter.hit("k", limit=3, window_ms=60_000)

    await limiter.reset("k")
    await limiter.hit("k", limit=3, window_ms=60_000)

    assert await redis_client.pttl("k") > 0
