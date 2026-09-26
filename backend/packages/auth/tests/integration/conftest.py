"""Fixtures for tests against a live PostgreSQL and Redis."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from live_db import db_engine, db_session, migrated_url
from redis.asyncio import Redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ("db_engine", "db_session", "migrated_url")


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    """Give a Redis client on an empty database from `TEST_REDIS_URL`."""
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL is not set, e.g. redis://localhost:6379/15")
    client = Redis.from_url(url, decode_responses=True)
    _ = await client.flushdb()
    yield client
    _ = await client.flushdb()
    await client.aclose()
