"""Settings of the migrator process."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from vld.core.config import settings_config


class MigratorSettings(BaseSettings):
    """Settings from `MIGRATOR_*`.

    Attributes:
        app_role: str - Role of the API: gets access to the rows of every domain.
        backup_dir: Path | None - Where dumps go before an upgrade.
        backup_keep: int - How many newest dumps to keep.
        pg_dump: str - `pg_dump` executable, not older than the server.
        lock_wait_seconds: float - How long to wait for another run to finish.
        lock_timeout_ms: int - Longest wait for a table lock inside a revision.
        statement_timeout_ms: int - Longest single statement of a revision.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("MIGRATOR_")

    app_role: str = Field(pattern=r"^[a-z_][a-z0-9_]*$")
    backup_dir: Path | None = None
    backup_keep: int = Field(default=5, ge=1)
    pg_dump: str = "pg_dump"
    lock_wait_seconds: float = Field(default=60, ge=0)
    lock_timeout_ms: int = Field(default=5_000, gt=0)
    statement_timeout_ms: int = Field(default=300_000, gt=0)

    @model_validator(mode="after")
    def _lock_timeout_below_statement_timeout(self) -> Self:
        """Refuse a lock timeout that the statement timeout would always beat.

        Returns:
            Self - The settings.

        Raises:
            ValueError: If `lock_timeout_ms` is not below `statement_timeout_ms`.

        """
        if self.lock_timeout_ms >= self.statement_timeout_ms:
            msg = "MIGRATOR_LOCK_TIMEOUT_MS must be below MIGRATOR_STATEMENT_TIMEOUT_MS"
            raise ValueError(msg)
        return self
