"""Redis connection settings."""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from pydantic import RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class RedisSettings(BaseSettings):
    """Redis settings.

    Attributes:
        dsn: RedisDsn - Redis address.
        cache_db: int - Logical database number for the cache.
        blacklist_db: int - Logical database number for the blacklist (JWT by jti).
        counters_db: int - Logical database number for the counters (viewers, etc.).

    """

    dsn: RedisDsn
    cache_db: int = 0
    blacklist_db: int = 1
    counters_db: int = 3

    model_config: ClassVar[SettingsConfigDict] = settings_config("REDIS_")


@lru_cache
def get_redis_settings() -> RedisSettings:
    """Get Redis settings.

    Returns:
        RedisSettings - Singleton on the process.

    """
    return RedisSettings()  # pyright: ignore[reportCallIssue]
