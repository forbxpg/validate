"""Password rules."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from vld.core.config import settings_config


class PasswordSettings(BaseSettings):
    """Settings from `PASSWORD_*`.

    Attributes:
        min_length: int - Fewest characters.
        min_uppercase: int - Fewest upper-case letters.
        min_lowercase: int - Fewest lower-case letters.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("PASSWORD_")

    min_length: int = Field(default=8, ge=1)
    min_uppercase: int = Field(default=1, ge=0)
    min_lowercase: int = Field(default=1, ge=0)
