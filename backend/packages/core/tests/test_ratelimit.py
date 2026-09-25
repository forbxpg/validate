"""Тесты ограничителя частоты запросов."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from redis.exceptions import RedisError

from vld.core.ratelimit import (
    RateLimiter,
    RateLimiterUnavailableError,
    RateLimitExceededError,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from vld.core.ratelimit._redis_port import RedisLike, RedisLikeScriptRunner


@pytest.mark.integration
async def test_allows_up_to_limit(redis_client: Redis) -> None:
    limiter = RateLimiter(redis_client)
    for _ in range(3):
        await limiter.hit("k", limit=3, window_ms=60_000)


@pytest.mark.integration
async def test_rejects_over_limit(redis_client: Redis) -> None:
    """Попытка сверх лимита отклоняется."""
    limiter = RateLimiter(redis_client)
    for _ in range(3):
        await limiter.hit("k", limit=3, window_ms=60_000)
    with pytest.raises(RateLimitExceededError):
        await limiter.hit("k", limit=3, window_ms=60_000)


@pytest.mark.integration
async def test_buckets_are_independent(redis_client: Redis) -> None:
    limiter = RateLimiter(redis_client)
    await limiter.hit("a", limit=1, window_ms=60_000)
    await limiter.hit("b", limit=1, window_ms=60_000)


@pytest.mark.integration
async def test_first_hit_sets_ttl(redis_client: Redis) -> None:
    limiter = RateLimiter(redis_client)
    await limiter.hit("k", limit=3, window_ms=60_000)

    ttl_ms = await redis_client.pttl("k")
    assert 0 < ttl_ms <= 60_000, f"ключ без TTL живёт вечно, pttl={ttl_ms}"


@pytest.mark.integration
async def test_the_window_is_fixed_not_sliding(redis_client: Redis) -> None:
    limiter = RateLimiter(redis_client)
    await limiter.hit("fixed", limit=10, window_ms=5_000)
    first_ttl = await redis_client.pttl("fixed")
    await asyncio.sleep(0.3)
    await limiter.hit("fixed", limit=10, window_ms=5_000)
    second_ttl = await redis_client.pttl("fixed")
    assert second_ttl < first_ttl, (
        f"окно продлилось: {first_ttl} -> {second_ttl}; это скользящее окно, "
        "в котором заблокированный клиент под нагрузкой не разблокируется никогда"
    )


class CountingRedis:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def register_script(self, script: str) -> RedisLikeScriptRunner:
        _ = script

        async def _call(keys: list[str], args: list[int]) -> list[int]:  # ruff: ignore[unused-async]
            key = keys[0]
            self._counts[key] = self._counts.get(key, 0) + 1
            return [self._counts[key], args[0]]

        return _call

    async def delete(self, *keys: str) -> int:
        return sum(self._counts.pop(key, None) is not None for key in keys)


class DeadRedis:
    def register_script(self, script: str) -> RedisLikeScriptRunner:
        _ = script

        async def _call(keys: list[str], args: list[int]) -> list[int]:  # ruff: ignore[unused-async]
            _ = (keys, args)
            msg = "connection refused"
            raise RedisError(msg)

        return _call

    async def delete(self, *keys: str) -> int:
        _ = keys
        msg = "connection refused"
        raise RedisError(msg)


async def test_fails_closed_when_redis_down() -> None:
    limiter = RateLimiter(DeadRedis())
    with pytest.raises(RateLimiterUnavailableError):
        await limiter.hit("k", limit=100, window_ms=60_000)


async def test_an_exhausted_limit_is_not_reported_as_an_outage() -> None:
    limiter = RateLimiter(CountingRedis())
    await limiter.hit("k", limit=1, window_ms=60_000)
    with pytest.raises(RateLimitExceededError) as caught:
        await limiter.hit("k", limit=1, window_ms=60_000)
    assert not isinstance(caught.value, RateLimiterUnavailableError)


async def test_reset_stays_quiet_when_redis_down() -> None:
    limiter = RateLimiter(DeadRedis())
    await limiter.reset("k")


@pytest.mark.integration
async def test_reset_clears_the_bucket(redis_client: Redis) -> None:
    limiter = RateLimiter(redis_client)
    for _ in range(3):
        await limiter.hit("k", limit=3, window_ms=60_000)
    with pytest.raises(RateLimitExceededError):
        await limiter.hit("k", limit=3, window_ms=60_000)

    await limiter.reset("k")

    await limiter.hit("k", limit=3, window_ms=60_000)
    ttl_ms = await redis_client.pttl("k")
    assert ttl_ms > 0, "сброшенный бакет обязан получить TTL заново"


if TYPE_CHECKING:
    _dead: RedisLike = DeadRedis()
    _counting: RedisLike = CountingRedis()
