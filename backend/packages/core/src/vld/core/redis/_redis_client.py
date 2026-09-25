"""Redis client on a specific logical database."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from redis.asyncio import Redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def redis_client(dsn: str, db: int) -> AsyncIterator[Redis]:
    """Open a Redis client on a specific logical database.

    Args:
        dsn: str - Redis address.
        db: int - Logical database number.

    Yields:
        Redis - Client, closed by the caller.

    """
    url = urlunsplit(urlsplit(dsn)._replace(path=f"/{db}"))
    client = Redis.from_url(url, decode_responses=True)  # pyright: ignore[reportUnknownMemberType]
    yield client
    await client.aclose()
