"""The address of the admin: the second and last origin, which the mutations trust."""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config
from ._base_url import normalized_base_url


class AdminSettings(BaseSettings):
    """The settings of the admin.

    Attributes:
        base_url: str | None - The base address of the admin, for example
            ``https://admin.example.com``.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("ADMIN_")

    base_url: str | None = None

    @field_validator("base_url")
    @classmethod
    def _must_carry_scheme_and_host(cls, value: str | None) -> str | None:
        """Check the address, if it is given.

        Args:
            value: str | None - Address from the environment or ``None``.

        Returns:
            str | None - Normalized address or ``None``.

        """
        if not value:
            return None
        return normalized_base_url(value)


@lru_cache
def get_admin_settings() -> AdminSettings:
    """Get the settings of the admin.

    Returns:
        AdminSettings - Singleton on the process.

    """
    return AdminSettings()
