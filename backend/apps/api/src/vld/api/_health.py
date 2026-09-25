"""Probes for the orchestrator: is the process alive, can it serve requests."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Protocol, cast

import structlog
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

if TYPE_CHECKING:
    from collections.abc import Awaitable

_CHECK_TIMEOUT_SECONDS = 2

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)

router = APIRouter(tags=["health"])


class _Pingable(Protocol):
    """`Redis.ping` with its untyped `**kwargs` left out."""

    def ping(self) -> Awaitable[bool]:
        """Ping the server.

        Returns:
            Awaitable[bool] - True when the server answered.

        """
        ...


@router.get("/health")
async def health() -> dict[str, str]:
    """Answer while the process runs, without touching any dependency.

    Returns:
        dict[str, str] - Always `{"status": "ok"}`.

    """
    return {"status": "ok"}


@router.get("/ready", response_model=None)
@inject
async def ready(
    engine: FromDishka[AsyncEngine],
    redis: FromDishka[Redis],
) -> JSONResponse:
    """Check that PostgreSQL and Redis answer, so traffic may be sent here.

    Args:
        engine: AsyncEngine - Application engine.
        redis: Redis - Application Redis client.

    Returns:
        JSONResponse - 200 when both answer, 503 otherwise, with each result.

    """
    database, cache = await asyncio.gather(
        _answers("database", _select_one(engine)),
        _answers("redis", cast("_Pingable", redis).ping()),
    )
    checks = {"database": database, "redis": cache}
    status = HTTPStatus.OK if all(checks.values()) else HTTPStatus.SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status,
        content={
            "status": "ready" if status == HTTPStatus.OK else "not_ready",
            **checks,
        },
    )


async def _select_one(engine: AsyncEngine) -> None:
    """Run the cheapest query on a pooled connection.

    Args:
        engine: AsyncEngine - Application engine.

    """
    async with engine.connect() as connection:
        _ = await connection.execute(text("SELECT 1"))


async def _answers(name: str, check: Awaitable[object]) -> bool:
    """Run one check with a timeout and report whether it passed.

    Args:
        name: str - Dependency name for the log.
        check: Awaitable[object] - The check itself.

    Returns:
        bool - True if the check finished in time without an error.

    """
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
            _ = await check
    except Exception:  # ruff: ignore[blind-except] -- a probe reports, it never fails
        _log.warning("readiness_check_failed", dependency=name, exc_info=True)
        return False
    return True
