"""Logging and monitoring settings."""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class ObservabilitySettings(BaseSettings):
    """Observability settings.

    Attributes:
        log_level: Literal - Logging level.
        log_json: bool - Write logs in JSON (for production) or human-readable.
        sentry_dsn: SecretStr | None - Sentry/GlitchTip DSN.

    """

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True
    sentry_dsn: SecretStr | None = None

    model_config: ClassVar[SettingsConfigDict] = settings_config("OBS_")


@lru_cache
def get_observability_settings() -> ObservabilitySettings:
    """Get observability settings.

    Returns:
        ObservabilitySettings - Singleton on the process.

    """
    return ObservabilitySettings()
