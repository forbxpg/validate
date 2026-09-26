"""Port of attempt limits."""

from __future__ import annotations

from typing import Protocol


class RateLimiter(Protocol):
    """Counter of attempts within a window."""

    async def hit(self, key: str, limit: int, window_ms: int) -> None:
        """Count an attempt and refuse it over the limit.

        Args:
            key: str - Bucket key, e.g. `login:email:<hash>`.
            limit: int - Attempts allowed per window.
            window_ms: int - Window length in milliseconds.

        Raises:
            RateLimitExceededError: If the limit is used up or the store is down.

        """
        ...

    async def reset(self, key: str) -> None:
        """Empty a bucket.

        Args:
            key: str - Bucket key.

        """
        ...
