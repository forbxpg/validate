"""The throttling provider builds the limiter on the application Redis client."""

from __future__ import annotations

from dishka import Provider, Scope, make_async_container, provide
from redis.asyncio import Redis

from vld.core.ratelimit import RateLimiter
from vld.web.throttling import Limiter
from vld.web.throttling.di import ThrottlingProvider

_REDIS = Redis(host="redis")


class _Redis(Provider):
    @provide(scope=Scope.APP)
    def redis(self) -> Redis:
        return _REDIS


async def test_the_limiter_uses_the_shared_redis_client() -> None:
    """One client per process: the limiter must not open a second one."""
    container = make_async_container(ThrottlingProvider(), _Redis())
    try:
        limiter = await container.get(Limiter)
    finally:
        await container.close()

    assert isinstance(limiter, RateLimiter)
    assert limiter._redis is _REDIS
