"""Origin check on mutating requests: the CSRF guard of the cookie transport."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from vld.core.config import CorsSettings
from vld.web.access import ACCESS_COOKIE, public
from vld.web.errors import CoreErrorCode, ErrorRegistry
from vld.web.mounting import DomainDescriptor, mount

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

SITE = "https://validate.example"
DEV_SITE = "http://localhost:3000"
FOREIGN = "https://evil.example"
MUTATING = ["POST", "PUT", "PATCH", "DELETE"]


class _StubError(Exception):
    pass


class _Settings(Provider):
    @provide(scope=Scope.APP)
    def cors(self) -> CorsSettings:
        return CorsSettings(allowed_origins=[SITE, DEV_SITE])


async def _thing() -> dict[str, str]:
    return {"ok": "yes"}


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Serve one public route for every method, trusting the site and the dev site."""
    router = APIRouter()
    _ = router.api_route("/thing", methods=[*MUTATING, "GET"], dependencies=[public()])(
        _thing,
    )
    app = FastAPI()
    errors = ErrorRegistry(_StubError, {}, CoreErrorCode.INTERNAL_ERROR)
    mount(app, DomainDescriptor(router=router, errors=errors, providers=()))
    setup_dishka(make_async_container(_Settings()), app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        yield ac


@pytest.mark.parametrize("method", MUTATING)
async def test_a_mutating_request_from_a_foreign_origin_is_refused(
    client: AsyncClient,
    method: str,
) -> None:
    """A foreign page cannot make the browser change state with our cookies."""
    response = await client.request(method, "/thing", headers={"Origin": FOREIGN})

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize("method", MUTATING)
@pytest.mark.parametrize("origin", [SITE, DEV_SITE])
async def test_every_trusted_origin_is_admitted(
    client: AsyncClient,
    method: str,
    origin: str,
) -> None:
    """Each listed origin passes, so an admin panel is one more list entry."""
    response = await client.request(method, "/thing", headers={"Origin": origin})

    assert response.status_code == HTTPStatus.OK


async def test_a_read_from_anywhere_is_still_a_read(client: AsyncClient) -> None:
    """Public lists stay readable from any page."""
    response = await client.get("/thing", headers={"Origin": FOREIGN})

    assert response.status_code == HTTPStatus.OK


async def test_a_program_without_origin_or_cookies_is_admitted(
    client: AsyncClient,
) -> None:
    """Curl and integrations send neither `Origin` nor cookies."""
    response = await client.post("/thing")

    assert response.status_code == HTTPStatus.OK


async def test_a_session_cookie_without_an_origin_is_refused(
    client: AsyncClient,
) -> None:
    """A cookie that claims no origin is ambient authority without proof."""
    response = await client.post("/thing", headers={"Cookie": f"{ACCESS_COOKIE}=x"})

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    ("referer", "expected"),
    [
        (f"{SITE}/journals/12", HTTPStatus.OK),
        (SITE, HTTPStatus.OK),
        (f"{DEV_SITE}/journals/12", HTTPStatus.OK),
        ("not-a-url", HTTPStatus.FORBIDDEN),
        (f"{FOREIGN}/journals/12", HTTPStatus.FORBIDDEN),
    ],
)
async def test_referer_is_the_fallback_when_origin_is_absent(
    client: AsyncClient,
    referer: str,
    expected: HTTPStatus,
) -> None:
    """Without `Origin` the request is judged by the origin of its `Referer`."""
    response = await client.post("/thing", headers={"Referer": referer})

    assert response.status_code == expected


@pytest.mark.parametrize(
    "claimed",
    [
        "https://evil.validate.example",
        "https://evil-validate.example",
        "https://validate.example.evil.example",
        "http://validate.example",
        "http://localhost",
        "http://localhost:8443",
        "null",
    ],
    ids=[
        "subdomain",
        "suffix",
        "prefix",
        "plain-http",
        "no-port",
        "other-port",
        "null",
    ],
)
async def test_an_origin_that_only_looks_like_ours_is_refused(
    client: AsyncClient,
    claimed: str,
) -> None:
    """Scheme, host and port are compared exactly, never by prefix or suffix."""
    response = await client.post("/thing", headers={"Origin": claimed})

    assert response.status_code == HTTPStatus.FORBIDDEN
