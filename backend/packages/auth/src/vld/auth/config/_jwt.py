"""Signing and lifetimes of the session tokens."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from vld.core.config import settings_config

MIN_JWT_SECRET_BYTES = 32
"""HS256 needs a key at least as long as its hash (RFC 7518, section 3.2)."""


class JwtSettings(BaseSettings):
    """Settings from `JWT_*`.

    Attributes:
        secret_key: SecretStr - `JWT_SECRET_KEY`, the HS256 signing key; also the
            key the links in letters are derived from.
        access_token_expires_minutes: int - Lifetime of an access token.
        refresh_token_expires_minutes: int - Lifetime of a refresh token.
        session_expires_days: int - Absolute ceiling of a session from the login;
            refreshing never moves it.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("JWT_")

    secret_key: SecretStr
    access_token_expires_minutes: int = Field(default=15, gt=0)
    refresh_token_expires_minutes: int = Field(default=30 * 24 * 60, gt=0)
    session_expires_days: int = Field(default=90, gt=0)

    @field_validator("secret_key")
    @classmethod
    def _secret_must_be_strong(cls, value: SecretStr) -> SecretStr:
        """Refuse a key too short for HS256.

        Args:
            value: SecretStr - Key from the environment.

        Returns:
            SecretStr - The same key.

        Raises:
            ValueError: If the key is shorter than 32 bytes.

        """
        if len(value.get_secret_value().encode()) < MIN_JWT_SECRET_BYTES:
            msg = f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_BYTES} bytes"
            raise ValueError(msg)
        return value

    @property
    def access_ttl(self) -> timedelta:
        """Lifetime of an access token.

        Returns:
            timedelta - The lifetime.

        """
        return timedelta(minutes=self.access_token_expires_minutes)

    @property
    def refresh_ttl(self) -> timedelta:
        """Lifetime of a refresh token.

        Returns:
            timedelta - The lifetime.

        """
        return timedelta(minutes=self.refresh_token_expires_minutes)

    @property
    def session_ttl(self) -> timedelta:
        """Absolute ceiling of a session.

        Returns:
            timedelta - The ceiling.

        """
        return timedelta(days=self.session_expires_days)
