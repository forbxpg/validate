"""Helpers of the crossref tests: virtual time."""

from __future__ import annotations

import asyncio


class FakeClock:
    """Monotonic time that moves only when the code under test sleeps."""

    def __init__(self) -> None:
        self.now: float = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        """Give the current virtual time."""
        return self.now

    async def sleep(self, seconds: float) -> None:
        """Move virtual time forward and let other tasks run."""
        self.sleeps.append(seconds)
        self.now += max(0.0, seconds)
        await asyncio.sleep(0)
