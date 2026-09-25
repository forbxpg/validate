"""The settings of the authentication and passwords."""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config

MIN_JWT_SECRET_BYTES = 32


class SecuritySettings(BaseSettings):
    """The settings of the security.

    Attributes:
        jwt_secret: SecretStr - The secret for the JWT signature.
        jwt_algorithm: str - The algorithm of the signature.
        access_ttl_seconds: int - The lifetime of the access token.
        refresh_ttl_seconds: int - The timeout of the refresh token.
        session_ttl_seconds: int - The absolute ceiling of the session from the login.
        password_min_length: int - The minimum length of the password.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("SECURITY_")

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_ttl_seconds: int = 60 * 15
    refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    session_ttl_seconds: int = 60 * 60 * 24 * 90
    password_min_length: int = 10

    @field_validator("jwt_secret")
    @classmethod
    def _secret_must_be_strong(cls, value: SecretStr) -> SecretStr:
        """Reject the empty and too short secret of the signature.

        Args:
            value: SecretStr - The secret from the environment.

        Returns:
            SecretStr - The same, if it is strong.

        Raises:
            ValueError: if the secret is shorter than 256 bits (including empty).

        """
        if len(value.get_secret_value().encode()) < MIN_JWT_SECRET_BYTES:
            msg = "jwt secret must be at least 256 bits."
            raise ValueError(msg)
        return value


@lru_cache
def get_security_settings() -> SecuritySettings:
    """Получить настройки безопасности.

    Returns:
        SecuritySettings - Синглтон на процесс.

    """
    return SecuritySettings()  # pyright: ignore[reportCallIssue]  # ty:ignore[missing-argument]
