"""The assembled API: probes, CORS and the request id, with dependencies down."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from vld.api.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

SITE = "https://validate.example"

pytestmark = pytest.mark.usefixtures("dead_dependencies")


@pytest.fixture
def dead_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the database and Redis at a port where nothing listens."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/validate")
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", "1")
    monkeypatch.setenv("MIDDLEWARE_CORS_ALLOWED_ORIGINS", f'["{SITE}"]')
    monkeypatch.setenv("JWT_SECRET_KEY", "k" * 32)
    monkeypatch.setenv("APP_ENV", "test")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Run the application through its lifespan and talk to it over ASGI."""
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac,
    ):
        yield ac


async def test_liveness_does_not_touch_dependencies(client: AsyncClient) -> None:
    """A database outage must not make the orchestrator restart the process."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_is_503_while_dependencies_are_down(
    client: AsyncClient,
) -> None:
    """Traffic stays away until PostgreSQL and Redis answer, and the body says which."""
    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": False, "redis": False}


async def test_a_trusted_origin_passes_the_preflight(client: AsyncClient) -> None:
    """The site may send credentialed requests from the browser."""
    response = await client.options(
        "/health",
        headers={"Origin": SITE, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == SITE
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_a_foreign_origin_fails_the_preflight(client: AsyncClient) -> None:
    """The browser gets no permission for a page that is not ours."""
    response = await client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


async def test_the_browser_may_read_the_request_id(client: AsyncClient) -> None:
    """A user reports the id from the page, so the browser must expose it."""
    response = await client.get("/health", headers={"Origin": SITE})

    assert response.headers["x-request-id"]
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


async def test_metrics_count_requests_by_route_and_status(client: AsyncClient) -> None:
    """Prometheus sees API traffic; the probes stay out of it."""
    _ = await client.get("/health")
    _ = await client.get("/api/v1/no-such-route")

    metrics = (await client.get("/metrics")).text

    assert (
        'http_requests_total{handler="none",method="GET",status="4xx"} 1.0' in metrics
    )
    assert 'handler="/health"' not in metrics
