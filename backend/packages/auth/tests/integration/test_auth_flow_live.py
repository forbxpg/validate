"""The whole API on live PostgreSQL and Redis: register, confirm, log in, log out."""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

import pytest
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs

from vld.api.main import create_app
from vld.auth.application import SendVerificationEmail
from vld.auth.domain import USER_REGISTERED_EVENT, DomainEvent
from vld.core.database import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from dishka import AsyncContainer
    from fastapi import FastAPI
    from redis.asyncio import Redis
    from sqlalchemy import URL

pytestmark = pytest.mark.integration

_ORIGIN = "https://validate.example"
_PASSWORD = "Correct Horse Battery"


@pytest.fixture
async def app(
    migrated_url: URL,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[FastAPI]:
    """Build the API from the environment, as in production, on the test stores."""
    redis = urlsplit(os.environ["TEST_REDIS_URL"])
    monkeypatch.setenv(
        "DATABASE_URL",
        migrated_url.render_as_string(hide_password=False),
    )
    monkeypatch.setenv("REDIS_HOST", redis.hostname or "localhost")
    monkeypatch.setenv("REDIS_PORT", str(redis.port or 6379))
    monkeypatch.setenv("REDIS_DB", redis.path.lstrip("/") or "0")
    monkeypatch.setenv("MIDDLEWARE_CORS_ALLOWED_ORIGINS", f'["{_ORIGIN}"]')
    monkeypatch.setenv("JWT_SECRET_KEY", secrets.token_hex(32))
    monkeypatch.setenv("APP_ENV", "test")
    del redis_client  # only its cleanup of the test database is needed
    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


async def _deliver_confirmation(app: FastAPI, user_id: str) -> str:
    """Run the handler the worker runs and read the token it logs."""
    container = cast("AsyncContainer", app.state.dishka_container)
    async with container() as scope:
        handler = await scope.get(SendVerificationEmail)
        uow = await scope.get(UnitOfWork)
        async with uow:
            recipient, token = await handler.prepare(
                DomainEvent(USER_REGISTERED_EVENT, {"user_id": user_id}),
                delivery_id=1,
            )
            await uow.commit()
        with capture_logs() as logs:
            await handler.deliver(recipient, token)
    [letter] = [entry for entry in logs if entry["event"] == "verification_email"]
    return cast("str", letter["token"])


async def test_register_confirm_login_and_logout(app: FastAPI) -> None:
    """A user goes the whole way on the real stores."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t/api/v1",
        headers={"Origin": _ORIGIN},
    ) as client:
        registered = await client.post(
            "/auth/register",
            json={
                "email": "Live@Example.org",
                "password": _PASSWORD,
                "role": "teacher",
            },
        )
        assert registered.status_code == 201, registered.text
        refused = await client.post(
            "/auth/login",
            json={"email": "live@example.org", "password": _PASSWORD},
        )
        assert refused.json()["error"] == "auth.email_not_verified"

        token = await _deliver_confirmation(app, registered.json()["user_id"])
        confirmed = await client.post("/auth/verify-email", json={"token": token})
        assert confirmed.status_code == 204

        login = await client.post(
            "/auth/login",
            json={"email": "live@example.org", "password": _PASSWORD},
        )
        assert login.status_code == 200, login.text
        pair = cast("dict[str, str]", login.json())
        headers = {"Authorization": f"Bearer {pair['access']}"}
        me = await client.get("/auth/me", headers=headers)
        assert me.json()["role"] == "teacher"
        assert me.json()["email_verified"] is True

        out = await client.post(
            "/auth/logout",
            json={"refresh": pair["refresh"]},
            headers=headers,
        )
        assert out.status_code == 204
        after = await client.get("/auth/me", headers=headers)
        assert after.json()["error"] == "auth.token_revoked"
