"""Base configuration for pydantic-settings for the whole project."""

from __future__ import annotations

from pydantic_settings import SettingsConfigDict


def settings_config(env_prefix: str) -> SettingsConfigDict:
    """Collect model_config for Settings with a custom environment prefix.

    Args:
        env_prefix: str - Environment prefix, e.g. `"DB_"` or `"AUDIT_"`.

    Returns:
        SettingsConfigDict - Configuration for the `model_config` field.

    """
    return SettingsConfigDict(
        env_prefix=env_prefix,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )
