"""SMTP of the letters with confirmation and reset links."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from vld.core.config import settings_config


class EmailSecurity(StrEnum):
    """How the SMTP connection is encrypted."""

    SSL = "ssl"
    STARTTLS = "starttls"


class EmailSettings(BaseSettings):
    """Settings from `EMAIL_*`.

    Without `EMAIL_HOST` the letters go to the worker log; that sender refuses
    to start in production.

    Attributes:
        host: str | None - SMTP host; Mailpit on the local stand.
        port: int | None - Port: 465 for SSL, 587 for STARTTLS, 1025 for Mailpit.
        security: EmailSecurity | None - Encryption; none for Mailpit.
        username: str | None - SMTP login.
        password: SecretStr | None - SMTP password.
        from_addr: str | None - Sender address.
        public_base_url: str | None - Site address the links in letters lead to.
        timeout: float - Seconds for one SMTP operation.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("EMAIL_")

    host: str | None = None
    port: int | None = None
    security: EmailSecurity | None = None
    username: str | None = None
    password: SecretStr | None = None
    from_addr: str | None = None
    public_base_url: str | None = None
    timeout: float = Field(default=10.0, gt=0)

    @property
    def is_configured(self) -> bool:
        """Say whether letters go over SMTP.

        Returns:
            bool - True when a host is set; `build_smtp_sender` checks the rest.

        """
        return self.host is not None
