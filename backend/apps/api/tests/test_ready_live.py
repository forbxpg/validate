"""Readiness against a live PostgreSQL and Redis."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from httpx import ASGITransport, AsyncClient

from vld.api.main import create_app

pytestmark = pytest.mark.integration


async def test_readiness_is_200_when_dependencies_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With both dependencies up the API takes traffic."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    redis_url = os.environ.get("TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip("TEST_DATABASE_URL and TEST_REDIS_URL are not set")
    redis = urlsplit(redis_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_HOST", redis.hostname or "localhost")
    monkeypatch.setenv("REDIS_PORT", str(redis.port or 6379))
    monkeypatch.setenv(
        "MIDDLEWARE_CORS_ALLOWED_ORIGINS", '["https://validate.example"]'
    )
    app = create_app()

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client,
    ):
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": True, "redis": True}
