"""Origins of the browser clients that the API trusts."""

from __future__ import annotations

from typing import ClassVar
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class CorsSettings(BaseSettings):
    """Trusted browser origins: the site, and the admin panel once there is one.

    Attributes:
        allowed_origins: list[str] - Origins such as `https://example.com`, as a JSON
            list in `MIDDLEWARE_CORS_ALLOWED_ORIGINS`.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("MIDDLEWARE_CORS_")

    allowed_origins: list[str]

    @field_validator("allowed_origins")
    @classmethod
    def _must_be_origins(cls, value: list[str]) -> list[str]:
        """Lower-case every origin so that it compares exactly with `Origin`.

        Args:
            value: list[str] - Origins from the environment.

        Returns:
            list[str] - The same origins, lower-cased.

        Raises:
            ValueError: If an entry is not a bare http(s) origin.

        """
        origins: list[str] = []
        for raw in value:
            parts = urlsplit(raw.lower())
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                msg = f"{raw!r} must look like https://example.com"
                raise ValueError(msg)
            if parts.path not in {"", "/"} or parts.query or parts.fragment:
                msg = f"{raw!r} is an origin and must not carry a path"
                raise ValueError(msg)
            origins.append(f"{parts.scheme}://{parts.netloc}")
        return origins
