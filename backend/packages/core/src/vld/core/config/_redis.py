"""Redis connection settings."""

from __future__ import annotations

from typing import ClassVar

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class RedisSettings(BaseSettings):
    """Redis settings.

    Attributes:
        host: str - Redis host.
        port: int - Redis port.
        db: int - Logical database number.
        username: str | None - ACL user, if Redis requires one.
        password: SecretStr | None - Password, if Redis requires one.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("REDIS_")

    host: str
    port: int = 6379
    db: int = 0
    username: str | None = None
    password: SecretStr | None = None
