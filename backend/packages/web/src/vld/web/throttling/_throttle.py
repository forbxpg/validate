"""Protocol of the rate limiter and two buckets by the client address."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

from vld.core.ratelimit import RateLimiterUnavailableError

from ._client_ip import client_ip

if TYPE_CHECKING:
    from starlette.requests import Request


class Limiter(Protocol):
    """Minimum from the rate limiter, needed by the throttling mechanics."""

    async def hit(self, key: str, limit: int, window_ms: int) -> None:
        """Count the attempt and reject it if the limit is exceeded.

        Args:
            key: str - Bucket key.
            limit: int - How many attempts are allowed per window.
            window_ms: int - Length of the window in milliseconds.

        Raises:
            RateLimiterUnavailableError - if the storage is not available.
            RateLimitExceededError - if the limit is exhausted.

        """
        ...


_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


async def throttle_by_ip(
    limiter: Limiter,
    request: Request,
    bucket: str,
    limit: int,
    window_ms: int,
) -> None:
    """Count the attempt from this address and reject it if the limit is exceeded.

    Args:
        limiter: Limiter - Rate limiter.
        request: Request - Request, from which the client address is taken.
        bucket: str - Bucket key, for example ``login``.
        limit: int - How many attempts are allowed per window.
        window_ms: int - Length of the window in milliseconds.

    Raises:
        RateLimiterUnavailableError - if the storage is not available.
        RateLimitExceededError - if the limit from this address is exhausted.

    """
    await limiter.hit(f"{bucket}:ip:{client_ip(request)}", limit, window_ms)


async def throttle_by_ip_fail_open(
    limiter: Limiter,
    request: Request,
    bucket: str,
    limit: int,
    window_ms: int,
) -> None:
    """Count the attempt, but do not drop public reading together with Redis.

    Args:
        limiter: Limiter - Rate limiter.
        request: Request - Request, from which the client address is taken.
        bucket: str - Bucket key, for example ``commerce_showcase``.
        limit: int - How many attempts are allowed per window.
        window_ms: int - Length of the window in milliseconds.

    Raises:
        RateLimitExceededError - if the limit from this address is exhausted.

    """
    try:
        await throttle_by_ip(limiter, request, bucket, limit, window_ms)
    except RateLimiterUnavailableError:
        _log.warning("throttle_unavailable", bucket=bucket)
