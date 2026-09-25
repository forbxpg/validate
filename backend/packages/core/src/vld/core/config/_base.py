"""The pydantic-settings configuration shared by every settings class."""

from __future__ import annotations

from pydantic_settings import SettingsConfigDict


def settings_config(env_prefix: str) -> SettingsConfigDict:
    """Build `model_config` for a settings class with its environment prefix.

    Variables come from the process environment only: a `.env` file is loaded by
    whoever starts the process (docker compose, `uv run --env-file`), not by the code.

    Args:
        env_prefix: str - Environment prefix, e.g. `"DATABASE_"`.

    Returns:
        SettingsConfigDict - Configuration for the `model_config` field.

    """
    return SettingsConfigDict(env_prefix=env_prefix, extra="ignore", frozen=True)
