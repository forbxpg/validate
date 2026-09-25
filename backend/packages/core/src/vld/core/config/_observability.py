"""Logging and error tracking settings."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class ObservabilitySettings(BaseSettings):
    """Observability settings, read without a prefix.

    Attributes:
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] - `LOG_LEVEL`.
        log_json: bool - `LOG_JSON`: JSON lines in production, console output
            otherwise.
        sentry_dsn: SecretStr | None - `SENTRY_DSN`: Sentry or GlitchTip, off when
            unset.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True
    sentry_dsn: SecretStr | None = None
