"""Helpers of the crossref tests: a fake Crossref, virtual time, fixtures."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, cast

import httpx

from vld.crossref import CrossrefClient, LocalThrottle, RateLimits, RetryPolicy

if TYPE_CHECKING:
    from collections.abc import Callable

    from vld.crossref import Throttle

FIXTURES = Path(__file__).parents[1] / "fixtures"
MAILTO = "test@example.org"
UNLIMITED = RateLimits(requests=1000, interval=timedelta(seconds=1), concurrency=None)


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


@dataclass
class Recorded:
    """A request the fake Crossref received."""

    method: str
    path: str
    params: dict[str, str]
    headers: dict[str, str]


type Reply = httpx.Response | Callable[[httpx.Request], httpx.Response]


@dataclass
class _Route:
    replies: list[Reply]
    repeat: bool


@dataclass
class FakeCrossref:
    """Answers by method and path.

    One reply repeats forever. Several are served once each, in order; after
    them the fake answers 410, so a walk that does not stop fails instead of
    hanging.
    """

    routes: dict[tuple[str, str], _Route] = field(default_factory=dict)
    requests: list[Recorded] = field(default_factory=list)

    def on(self, method: str, path: str, *replies: Reply) -> FakeCrossref:
        """Register replies for a method and path."""
        self.routes[method, path] = _Route(list(replies), repeat=len(replies) == 1)
        return self

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """Serve one request."""
        self.requests.append(
            Recorded(
                method=request.method,
                path=request.url.path,
                params=dict(request.url.params),
                headers=dict(request.headers),
            ),
        )
        route = self.routes.get((request.method, request.url.path))
        if route is None:
            return httpx.Response(404, text="Resource not found.")
        if not route.replies:
            return httpx.Response(410, text="the fake has no more replies")
        reply = route.replies[0] if route.repeat else route.replies.pop(0)
        return reply(request) if callable(reply) else reply


def ok(message: object, **headers: str) -> httpx.Response:
    """A 200 envelope around a message."""
    body = {
        "status": "ok",
        "message-type": "test",
        "message-version": "1.0.0",
        "message": message,
    }
    return httpx.Response(200, json=body, headers=headers)


def listing(
    items: list[object],
    *,
    total: int | None = None,
    cursor: str | None = None,
) -> httpx.Response:
    """A 200 list envelope."""
    message: dict[str, object] = {
        "items": items,
        "total-results": len(items) if total is None else total,
        "items-per-page": len(items),
        "query": {"start-index": 0, "search-terms": None},
    }
    if cursor is not None:
        message["next-cursor"] = cursor
    return ok(message)


def make_client(
    fake: FakeCrossref,
    *,
    clock: FakeClock | None = None,
    throttle: Throttle | None = None,
    retry: RetryPolicy | None = None,
) -> CrossrefClient:
    """A client over the fake Crossref, in virtual time, jitter at its maximum."""
    clock = clock or FakeClock()
    return CrossrefClient(
        mailto=MAILTO,
        throttle=throttle or LocalThrottle(UNLIMITED, clock=clock, sleep=clock.sleep),
        app="tests/1.0",
        retry=retry or RetryPolicy(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(fake)),
        clock=clock,
        sleep=clock.sleep,
        rng=lambda: 1.0,
    )


def fixture(name: str) -> object:
    """A recorded Crossref answer from ``tests/fixtures/<name>.json``."""
    return cast("object", json.loads((FIXTURES / f"{name}.json").read_text()))
