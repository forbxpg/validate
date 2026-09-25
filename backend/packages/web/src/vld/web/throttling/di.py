"""Rate limiter provider: binds the throttling protocol to the Redis limiter."""

from __future__ import annotations

from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from vld.core.ratelimit import RateLimiter
from vld.web.throttling import Limiter


class ThrottlingProvider(Provider):
    """Rate limiter shared by every domain."""

    @provide(scope=Scope.APP)
    def limiter(self, redis: Redis) -> Limiter:
        """Build the rate limiter on the application Redis client.

        Args:
            redis: Redis - Client from `CoreProvider`.

        Returns:
            Limiter - Fixed-window limiter on top of Redis.

        """
        return RateLimiter(redis)
