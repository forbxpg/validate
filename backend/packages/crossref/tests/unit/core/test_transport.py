"""One request: identity, the meaning of each status, retries and limits."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from crossref_support import MAILTO, FakeClock, FakeCrossref, make_client, ok
from pydantic import SecretStr

from vld.crossref import (
    CrossrefBadRequestError,
    CrossrefBlockedError,
    CrossrefClient,
    CrossrefRateLimitedError,
    CrossrefSchemaError,
    CrossrefUnavailableError,
    LocalThrottle,
    RateLimits,
    RetryPolicy,
    ValidationProblem,
)
from vld.crossref.transport import VERSION, Identity


def test_the_user_agent_names_the_app_the_address_and_the_library() -> None:
    """Crossref sees who calls, with and without an address."""
    polite = Identity(mailto=" a@b.org ", plus_token=None, app="validate/1.0")
    public = Identity(mailto=None, plus_token=None, app="validate/1.0")

    assert polite.headers() == {
        "User-Agent": f"validate/1.0 (mailto:a@b.org) vld-crossref/{VERSION}",
    }
    assert polite.params() == {"mailto": "a@b.org"}
    assert public.headers() == {"User-Agent": f"validate/1.0 vld-crossref/{VERSION}"}
    assert public.params() == {}


def test_the_plus_token_goes_into_its_own_header() -> None:
    """Metadata Plus is a bearer token header."""
    identity = Identity(mailto=None, plus_token=SecretStr("secret"), app="validate/1.0")

    assert identity.headers()["Crossref-Plus-API-Token"] == "Bearer secret"


@pytest.mark.parametrize(
    ("mailto", "app"),
    [("", "a/1"), ("nobody", "a/1"), (None, "validate"), (None, "a b/1")],
)
def test_an_identity_crossref_would_not_accept_is_refused(
    mailto: str | None,
    app: str,
) -> None:
    """A blank address or an app without a version is a mistake of the caller."""
    with pytest.raises(ValueError, match=r"mailto|app"):
        _ = Identity(mailto=mailto, plus_token=None, app=app)


async def test_a_request_carries_the_identity_and_its_parameters() -> None:
    """Parameters of the resource and mailto reach Crossref."""
    fake = FakeCrossref().on("GET", "/works", ok({"items": []}))

    async with make_client(fake) as client:
        envelope = await client._transport.get_json("/works", {"query": "x"})

    assert envelope is not None
    assert envelope.message == {"items": []}
    [sent] = fake.requests
    assert sent.params == {"query": "x", "mailto": MAILTO}
    assert sent.headers["user-agent"].startswith("tests/1.0 (mailto:test@example.org)")


async def test_404_is_none_and_head_is_false() -> None:
    """Not found is an answer, not an error."""
    fake = FakeCrossref().on("HEAD", "/works/10.1/a", httpx.Response(200))

    async with make_client(fake) as client:
        assert await client._transport.get_json("/works/10.1/missing", {}) is None
        assert await client._transport.head("/works/10.1/a") is True
        assert await client._transport.head("/works/10.1/missing") is False


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>maintenance</html>"),
        httpx.Response(200, json=[1, 2]),
        httpx.Response(200, json={"status": "failed", "message": []}),
        httpx.Response(200, json={"status": "ok"}),
    ],
    ids=["html", "not-object", "failed", "no-message"],
)
async def test_a_broken_envelope_is_a_schema_error(response: httpx.Response) -> None:
    """Without an envelope there is nothing to return."""
    fake = FakeCrossref().on("GET", "/works", response)

    async with make_client(fake) as client:
        with pytest.raises(CrossrefSchemaError, match="/works"):
            _ = await client._transport.get_json("/works", {})


async def test_400_lists_the_complaints_of_crossref_and_is_not_retried() -> None:
    """A validation failure carries its problems."""
    body = {
        "status": "failed",
        "message-type": "validation-failure",
        "message": [
            {
                "type": "filter-not-available",
                "value": "zzz",
                "message": "no such filter",
            },
        ],
    }
    fake = FakeCrossref().on("GET", "/works", httpx.Response(400, json=body))

    async with make_client(fake) as client:
        with pytest.raises(CrossrefBadRequestError) as caught:
            _ = await client._transport.get_json("/works", {"filter": "zzz:1"})

    assert caught.value.problems == (
        ValidationProblem("filter-not-available", "zzz", "no such filter"),
    )
    assert len(fake.requests) == 1
    assert caught.value.url is not None
    assert MAILTO not in caught.value.url


async def test_403_is_a_block_and_is_not_retried() -> None:
    """A manual block does not go away by asking again."""
    fake = FakeCrossref().on("GET", "/works", httpx.Response(403))

    async with make_client(fake) as client:
        with pytest.raises(CrossrefBlockedError):
            _ = await client._transport.get_json("/works", {})

    assert len(fake.requests) == 1


async def test_429_waits_as_long_as_crossref_asks_and_then_succeeds() -> None:
    """Retry-After in seconds is honoured."""
    clock = FakeClock()
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(429, headers={"retry-after": "2"}),
        ok({"items": []}),
    )

    async with make_client(fake, clock=clock) as client:
        envelope = await client._transport.get_json("/works", {})

    assert envelope is not None
    assert 2.0 in clock.sleeps
    assert len(fake.requests) == 2


async def test_5xx_backs_off_exponentially_up_to_the_ceiling() -> None:
    """Without Retry-After the waits double and stop at max_wait."""
    clock = FakeClock()
    fake = FakeCrossref().on("GET", "/works", httpx.Response(503))
    policy = RetryPolicy(
        attempts=5,
        base_wait=timedelta(seconds=1),
        max_wait=timedelta(seconds=5),
    )

    async with make_client(fake, clock=clock, retry=policy) as client:
        with pytest.raises(CrossrefUnavailableError) as caught:
            _ = await client._transport.get_json("/works", {})

    assert caught.value.status == 503
    assert [s for s in clock.sleeps if s > 0] == [1.0, 2.0, 4.0, 5.0]
    assert len(fake.requests) == 5


async def test_429_that_never_ends_is_a_rate_limit_error() -> None:
    """When the attempts run out the caller learns how long Crossref asked to wait."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(429, headers={"retry-after": "7"}),
    )

    async with make_client(fake, retry=RetryPolicy(attempts=2)) as client:
        with pytest.raises(CrossrefRateLimitedError) as caught:
            _ = await client._transport.get_json("/works", {})

    assert caught.value.retry_after == pytest.approx(7.0)


async def test_a_broken_connection_is_retried_then_unavailable() -> None:
    """Timeouts and dropped connections are transient."""

    def _drop(request: httpx.Request) -> httpx.Response:
        msg = "refused"
        raise httpx.ConnectError(msg, request=request)

    fake = FakeCrossref().on("GET", "/works", _drop)

    async with make_client(fake, retry=RetryPolicy(attempts=3)) as client:
        with pytest.raises(CrossrefUnavailableError) as caught:
            _ = await client._transport.get_json("/works", {})

    assert caught.value.status is None
    assert len(fake.requests) == 3


async def test_an_unexpected_status_is_unavailable_without_retries() -> None:
    """A 418 is not worth asking again."""
    fake = FakeCrossref().on("GET", "/works", httpx.Response(418))

    async with make_client(fake) as client:
        with pytest.raises(CrossrefUnavailableError):
            _ = await client._transport.get_json("/works", {})

    assert len(fake.requests) == 1


async def test_every_attempt_takes_a_slot_and_teaches_the_limits() -> None:
    """Retries pass the throttle again; reported limits reach it."""
    clock = FakeClock()
    throttle = LocalThrottle(RateLimits.PUBLIC, clock=clock, sleep=clock.sleep)
    polite = {
        "x-rate-limit-limit": "10",
        "x-rate-limit-interval": "1s",
        "x-concurrency-limit": "3",
        "x-api-pool": "polite",
    }
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(503, headers=polite),
        ok({}, **polite),
    )

    async with make_client(fake, clock=clock, throttle=throttle) as client:
        _ = await client._transport.get_json("/works", {})
        assert client.pool == "polite"

    assert throttle.limits == RateLimits(10, timedelta(seconds=1), 3, "polite")
    assert len(fake.requests) == 2


async def test_the_own_http_client_is_closed_and_a_given_one_is_not() -> None:
    """The library closes only what it opened."""
    given = httpx.AsyncClient(transport=httpx.MockTransport(FakeCrossref()))
    client = CrossrefClient(
        mailto=None,
        throttle=LocalThrottle(),
        app="tests/1.0",
        http=given,
    )

    async with client:
        pass

    assert not given.is_closed
    await given.aclose()


async def test_the_client_refuses_to_work_outside_async_with() -> None:
    """Forgetting async with is a clear error, not a hang."""
    client = make_client(FakeCrossref())

    with pytest.raises(RuntimeError, match="async context manager"):
        _ = await client._transport.get_json("/works", {})


async def test_the_own_http_client_is_closed_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client opened by the library does not leak its connections."""
    closed: list[httpx.AsyncClient] = []
    original = httpx.AsyncClient.aclose

    async def _aclose(self: httpx.AsyncClient) -> None:
        closed.append(self)
        await original(self)

    monkeypatch.setattr(httpx.AsyncClient, "aclose", _aclose)

    async with CrossrefClient(mailto=None, throttle=LocalThrottle(), app="tests/1.0"):
        pass

    assert len(closed) == 1
