"""Dependency injection of auth: settings, adapters and use cases."""

from __future__ import annotations

from ._adapters import AuthAdapterProvider
from ._settings import AuthSettingsProvider
from ._use_cases import (
    AuthAccountUseCaseProvider,
    AuthAdministrationUseCaseProvider,
    AuthOnboardingUseCaseProvider,
    AuthPasswordUseCaseProvider,
    AuthSessionUseCaseProvider,
)

__all__ = (
    "AuthAccountUseCaseProvider",
    "AuthAdapterProvider",
    "AuthAdministrationUseCaseProvider",
    "AuthOnboardingUseCaseProvider",
    "AuthPasswordUseCaseProvider",
    "AuthSessionUseCaseProvider",
    "AuthSettingsProvider",
)
