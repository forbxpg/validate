"""Where the process runs."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class AppSettings(BaseSettings):
    """Settings from `APP_*`.

    Attributes:
        env: Literal["local", "test", "production"] - `APP_ENV`. Production unless
            set: whatever is only safe on a laptop must be asked for explicitly.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("APP_")

    env: Literal["local", "test", "production"] = "production"
