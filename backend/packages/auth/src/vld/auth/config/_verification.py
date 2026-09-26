"""Whether a login waits for the address to be confirmed."""

from __future__ import annotations

from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

from vld.core.config import settings_config


class VerificationSettings(BaseSettings):
    """Settings from `AUTH_*`.

    Attributes:
        require_email_verification: bool - `AUTH_REQUIRE_EMAIL_VERIFICATION`. On
            unless turned off: a forgotten variable makes the service stricter.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("AUTH_")

    require_email_verification: bool = True
