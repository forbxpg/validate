"""Limits of one process: a sliding window of requests and a count of places."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, final

from ._port import RateLimits

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable


@final
class LocalThrottle:
    """Limits of one event loop of one process.

    It starts with the limits it is given and takes the limits Crossref reports.
    Two instances share nothing: clients that must share a limit share the object.
    """

    def __init__(
        self,
        initial: RateLimits = RateLimits.PUBLIC,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._limits: RateLimits = initial
        self._clock: Callable[[], float] = clock
        self._sleep: Callable[[float], Awaitable[None]] = sleep
        self._entries: deque[float] = deque()
        self._inside: int = 0
        self._changed: asyncio.Condition = asyncio.Condition()

    @property
    def limits(self) -> RateLimits:
        """Limits in force.

        Returns:
            RateLimits - The limits.

        """
        return self._limits

    @asynccontextmanager
    async def slot(self) -> AsyncGenerator[None]:
        """Wait for a free place and a rate token; hold the place until the block ends.

        Yields:
            None - While the request is in flight.

        """
        async with self._changed:
            _ = await self._changed.wait_for(self._has_room)
            self._inside += 1
        try:
            await self._take_token()
            yield
        finally:
            async with self._changed:
                self._inside -= 1
                self._changed.notify_all()

    async def observe(self, limits: RateLimits) -> None:
        """Take the limits of the last response for the next requests.

        Args:
            limits: RateLimits - Limits Crossref reported.

        """
        async with self._changed:
            self._limits = limits
            self._changed.notify_all()

    def _has_room(self) -> bool:
        limit = self._limits.concurrency
        return limit is None or self._inside < limit

    async def _take_token(self) -> None:
        while True:
            window = self._limits.interval.total_seconds()
            now = self._clock()
            while self._entries and self._entries[0] <= now - window:
                _ = self._entries.popleft()
            if len(self._entries) < self._limits.requests:
                self._entries.append(now)
                return
            await self._sleep(self._entries[0] + window - now)
