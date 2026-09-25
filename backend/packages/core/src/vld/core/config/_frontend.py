"""The address of the frontend: one for the whole process, read by two."""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config
from ._base_url import normalized_base_url


class FrontendSettings(BaseSettings):
    """The settings of the frontend.

    Attributes:
        base_url: str - The base URL of the frontend, for example `https://example.com`.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("FRONTEND_")

    base_url: str

    @field_validator("base_url")
    @classmethod
    def _must_carry_scheme_and_host(cls, value: str) -> str:
        """Reject the address from which the origin cannot be collected and bring the register.

        Args:
            value: str - The address from the environment.

        Returns:
            str - The same.

        """  # ruff: ignore[line-too-long]
        return normalized_base_url(value)


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    """Get the settings of the frontend.

    Returns:
        FrontendSettings - Singleton for the process.

    """
    return FrontendSettings()  # pyright: ignore[reportCallIssue]
