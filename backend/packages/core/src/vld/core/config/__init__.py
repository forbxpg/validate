"""Settings read from the environment, one class per concern."""

from __future__ import annotations

from ._app import AppSettings
from ._base import settings_config
from ._cors import CorsSettings
from ._database import DatabaseSettings
from ._observability import ObservabilitySettings
from ._redis import RedisSettings

__all__ = (
    "AppSettings",
    "CorsSettings",
    "DatabaseSettings",
    "ObservabilitySettings",
    "RedisSettings",
    "settings_config",
)
