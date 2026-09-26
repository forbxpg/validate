"""Dependency injection of auth: settings, adapters and use cases."""

from __future__ import annotations

from ._adapters import AuthAdapterProvider
from ._settings import AuthSettingsProvider
from ._use_cases import AuthOnboardingUseCaseProvider

__all__ = (
    "AuthAdapterProvider",
    "AuthOnboardingUseCaseProvider",
    "AuthSettingsProvider",
)
