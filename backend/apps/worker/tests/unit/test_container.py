"""The container of the worker builds from the environment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.worker import build_container

if TYPE_CHECKING:
    import pytest


async def test_the_container_builds_and_validates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every handler of the map can be built from the providers of the worker."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/validate")
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("JWT_SECRET_KEY", "k" * 32)
    monkeypatch.setenv("APP_ENV", "test")

    container = build_container()

    await container.close()
