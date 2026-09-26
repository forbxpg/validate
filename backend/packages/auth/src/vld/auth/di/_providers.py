"""The whole set of auth providers."""

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

AUTH_PROVIDERS = (
    AuthSettingsProvider(),
    AuthAdapterProvider(),
    AuthOnboardingUseCaseProvider(),
    AuthSessionUseCaseProvider(),
    AuthPasswordUseCaseProvider(),
    AuthAccountUseCaseProvider(),
    AuthAdministrationUseCaseProvider(),
)
"""Every provider of the domain: the API, the worker and the console need them all."""
