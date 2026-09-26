"""Port of the limits: what a request needs before it may leave."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager


@dataclass(frozen=True, slots=True)
class RateLimits:
    """Limits of a Crossref pool.

    Attributes:
        requests: int - Requests allowed per interval.
        interval: timedelta - Length of the interval.
        concurrency: int | None - Requests allowed at once; None for no limit.
        pool: str | None - Name of the pool, from ``x-api-pool``.

    """

    requests: int
    interval: timedelta
    concurrency: int | None
    pool: str | None = None

    PUBLIC: ClassVar[RateLimits]
    POLITE: ClassVar[RateLimits]
    PLUS: ClassVar[RateLimits]

    def __post_init__(self) -> None:
        """Refuse limits that would stop every request.

        Raises:
            ValueError: If a count is below one or the interval is not positive.

        """
        if self.requests < 1 or self.interval <= timedelta(0):
            msg = f"unusable rate: {self.requests} per {self.interval}"
            raise ValueError(msg)
        if self.concurrency is not None and self.concurrency < 1:
            msg = f"unusable concurrency: {self.concurrency}"
            raise ValueError(msg)


RateLimits.PUBLIC = RateLimits(5, timedelta(seconds=1), 1, "public")
RateLimits.POLITE = RateLimits(10, timedelta(seconds=1), 3, "polite")
RateLimits.PLUS = RateLimits(150, timedelta(seconds=1), None, "plus")


class Throttle(Protocol):
    """What the transport asks before every attempt and tells after it."""

    def slot(self) -> AbstractAsyncContextManager[None]:
        """Wait for a free place and a rate token; hold the place until the block ends.

        Returns:
            AbstractAsyncContextManager[None] - The place, held by ``async with``.

        """
        ...

    async def observe(self, limits: RateLimits) -> None:
        """Take the limits of the last response for the next requests.

        Args:
            limits: RateLimits - Limits Crossref reported.

        """
        ...
