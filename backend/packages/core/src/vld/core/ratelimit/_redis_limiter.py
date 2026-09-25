"""Rate limiting requests through Redis (fixed window)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from redis.exceptions import RedisError

if TYPE_CHECKING:
    from ._redis_port import RedisLike, RedisLikeScriptRunner


_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


class RateLimitExceededError(Exception):
    """The request limit has been exceeded or the storage is unavailable.

    Attributes:
        retry_after: int - How many seconds to wait before trying again.

    """

    def __init__(self, retry_after: int) -> None:
        self.retry_after: int = retry_after
        super().__init__("rate limit exceeded")


class RateLimiterUnavailableError(RateLimitExceededError):
    """The storage of the limiter is unavailable.

    Attributes:
        retry_after: int - How many seconds to wait before trying again.

    """


_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('PTTL', KEYS[1])}
"""


class RateLimiter:
    """A counter of requests with a fixed window on top of Redis.

    Attributes:
        _script: RedisLikeScriptRunner - Compiled Lua script.
        _redis: RedisLike - Redis client, needed to reset the bucket.

    """

    _script: RedisLikeScriptRunner
    _redis: RedisLike
    _SECOND_MS: int = 1000

    def __init__(self, redis: RedisLike) -> None:
        self._script = redis.register_script(_SCRIPT)
        self._redis = redis

    async def hit(self, key: str, limit: int, window_ms: int) -> None:
        """Count the attempt and reject it if the limit is exceeded.

        Args:
            key: str - The bucket key, for example `login:ip:1.2.3.4`.
            limit: int - How many attempts are allowed per window.
            window_ms: int - The length of the window in milliseconds.

        Raises:
            RateLimiterUnavailableError: if Redis is unavailable.
            RateLimitExceededError: if the limit is exceeded.

        """
        try:
            count, ttl_ms = await self._script(keys=[key], args=[window_ms])
        except RedisError as exc:
            raise RateLimiterUnavailableError(
                max(1, window_ms // self._SECOND_MS)
            ) from exc
        if count > limit:
            raise RateLimitExceededError(max(1, ttl_ms // self._SECOND_MS))

    async def reset(self, key: str) -> None:
        """Reset the bucket.

        Args:
            key: str - The bucket key.

        """
        try:
            _ = await self._redis.delete(key)
        except RedisError:
            _log.warning("rate_limit_reset_failed", key=key)
