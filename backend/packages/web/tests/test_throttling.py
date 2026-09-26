"""Throttling by client address and its fail-open mode."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from structlog.testing import capture_logs

from vld.core.ratelimit import RateLimiterUnavailableError, RateLimitExceededError
from vld.web.throttling import _client_ip as client_ip_module
from vld.web.throttling import client_ip, throttle_by_ip, throttle_by_ip_fail_open


class _RecordingLimiter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error: Exception | None = error
        self.keys: list[str] = []

    async def hit(self, key: str, limit: int, window_ms: int) -> None:
        del limit, window_ms
        self.keys.append(key)
        if self.error is not None:
            raise self.error


def _request(client: tuple[str, int] | None) -> Request:
    return Request({"type": "http", "client": client, "headers": []})


def test_client_ip_is_the_transport_address() -> None:
    """The proxy in front rewrites the address, so the transport one is trusted."""
    assert client_ip(_request(("1.2.3.4", 555))) == "1.2.3.4"


def test_an_unknown_client_is_warned_about_once() -> None:
    """Behind a unix socket every client shares one bucket, which must be loud."""
    client_ip_module._warn_unknown_client.cache_clear()

    with capture_logs() as logs:
        first = client_ip(_request(None))
        second = client_ip(_request(None))

    assert (first, second) == ("unknown", "unknown")
    warnings = [log for log in logs if log["event"] == "client_address_unknown"]
    assert [log["log_level"] for log in warnings] == ["warning"]


async def test_the_bucket_key_carries_the_bucket_and_the_address() -> None:
    """Buckets of different routes and clients never share a counter."""
    limiter = _RecordingLimiter()

    await throttle_by_ip(limiter, _request(("1.2.3.4", 555)), "journals", 60, 60_000)

    assert limiter.keys == ["journals:ip:1.2.3.4"]


async def test_a_dead_store_lets_the_request_through_and_says_so() -> None:
    """A Redis outage keeps public reads open, with a warning per bucket."""
    limiter = _RecordingLimiter(RateLimiterUnavailableError(retry_after=1))

    with capture_logs() as logs:
        await throttle_by_ip_fail_open(
            limiter,
            _request(("1.2.3.4", 555)),
            "journals",
            60,
            60_000,
        )

    warnings = [log for log in logs if log["event"] == "throttle_unavailable"]
    assert [(log["log_level"], log["bucket"]) for log in warnings] == [
        ("warning", "journals"),
    ]


async def test_fail_open_still_refuses_an_exhausted_limit() -> None:
    """Fail-open survives a dead store only; the limit itself still holds."""
    limiter = _RecordingLimiter(RateLimitExceededError(retry_after=1))

    with pytest.raises(RateLimitExceededError):
        await throttle_by_ip_fail_open(
            limiter,
            _request(("1.2.3.4", 555)),
            "journals",
            0,
            60_000,
        )
