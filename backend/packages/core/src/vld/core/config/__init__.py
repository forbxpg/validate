"""Configuration package."""

from __future__ import annotations

from ._database import DatabaseSettings
from ._observability import ObservabilitySettings

__all__ = ("DatabaseSettings", "ObservabilitySettings")
