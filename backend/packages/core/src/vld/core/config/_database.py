"""PostgreSQL connection settings."""

from __future__ import annotations

from typing import ClassVar

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class DatabaseSettings(BaseSettings):
    """Database settings.

    Attributes:
        url: PostgresDsn - Connection URL, `postgresql+asyncpg://...`.
        echo: bool - Log every SQL statement.
        pool_size: int - Connections kept open per process.
        max_overflow: int - Connections allowed above the pool size.
        pool_timeout: int - Seconds to wait for a free connection.
        pool_pre_ping: bool - Check a connection before handing it out.
        pool_recycle: int - Seconds after which a connection is reopened.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("DATABASE_")

    url: PostgresDsn
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_pre_ping: bool = True
    pool_recycle: int = 1800
