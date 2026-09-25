from __future__ import annotations

from typing import ClassVar

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class DatabaseSettings(BaseSettings):
    """Database settings.

    Attributes:
        dsn: PostgresDsn - Main DSN, through PgBouncer.
        direct_dsn: PostgresDsn | None - DSN directly to PostgreSQL, bypassing the pool.
        echo: bool - Log SQL.
        pool_size: int - Size of the pool per process (over PgBouncer).
        max_overflow: int - How many connections over the pool are allowed.
        pool_pre_ping: bool - Ping the connection before issuing.
        disable_prepared_statements: bool - Emergency flag for PgBouncer < 1.21, which
            doesn't understand prepared statements in transaction-mode.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("DB_")

    dsn: PostgresDsn
    direct_dsn: PostgresDsn | None = None

    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 10
    pool_pre_ping: bool = True
    disable_prepared_statements: bool = False

    @property
    def migration_dsn(self) -> str:
        """DSN for Alembic.

        Returns:
            str - Direct DSN, if set, otherwise main.

        """
        return str(self.direct_dsn or self.dsn)
