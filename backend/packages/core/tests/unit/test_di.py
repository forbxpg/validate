"""The core container builds its graph from the environment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dishka import make_async_container
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from vld.core.config import CorsSettings
from vld.core.database import SqlAlchemyUnitOfWork, UnitOfWork
from vld.core.di import CONTAINER_VALIDATION, CoreProvider

if TYPE_CHECKING:
    import pytest


async def test_the_core_graph_resolves_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings, Redis, session and unit of work all come out of one container."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/validate")
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv(
        "MIDDLEWARE_CORS_ALLOWED_ORIGINS", '["https://validate.example"]'
    )
    container = make_async_container(
        CoreProvider(),
        validation_settings=CONTAINER_VALIDATION,
    )
    try:
        async with container() as request:
            uow = await request.get(UnitOfWork)
            session = await request.get(AsyncSession)
        cors = await container.get(CorsSettings)
        redis = await container.get(Redis)
    finally:
        await container.close()

    assert isinstance(uow, SqlAlchemyUnitOfWork)
    assert uow.session is session, "the unit of work must share the request session"
    assert cors.allowed_origins == ["https://validate.example"]
    assert redis.connection_pool.connection_kwargs["host"] == "redis"
