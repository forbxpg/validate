"""SMTP sender over aiosmtplib."""

from __future__ import annotations

from email.message import EmailMessage
from typing import TYPE_CHECKING

import aiosmtplib
import structlog
from aiosmtplib import (
    SMTPAuthenticationError,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPSenderRefused,
)

from vld.auth.application import EmailPermanentlyUndeliverableError
from vld.auth.config import EmailSecurity

from ._content import render_password_reset_email, render_verification_email

if TYPE_CHECKING:
    from pydantic import SecretStr

    from vld.auth.config import EmailSettings

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)

_VERIFY_PATH = "/auth/verify-email"
_RESET_PATH = "/auth/password/new"
# Mailpit of the local stand takes plain SMTP without a login; no other host does.
_LOCAL_CATCHER_HOSTS = frozenset({"127.0.0.1", "localhost", "mailpit"})
_PERMANENT_CLASS = 5


class EmailMisconfiguredError(RuntimeError):
    """SMTP is on (a host is set) but the settings are incomplete."""


def build_smtp_sender(settings: EmailSettings) -> SmtpEmailSender:
    """Build the SMTP sender, refusing incomplete settings at startup.

    Args:
        settings: EmailSettings - Settings with a host set.

    Returns:
        SmtpEmailSender - The sender.

    Raises:
        EmailMisconfiguredError: If a required setting is missing.

    """
    host, port = settings.host, settings.port
    from_addr, base = settings.from_addr, settings.public_base_url
    if host is None or port is None or from_addr is None or base is None:
        msg = (
            "EMAIL_HOST, EMAIL_PORT, EMAIL_FROM_ADDR and EMAIL_PUBLIC_BASE_URL "
            "are required"
        )
        raise EmailMisconfiguredError(msg)
    remote = host not in _LOCAL_CATCHER_HOSTS
    credentials = (settings.security, settings.username, settings.password)
    if remote and None in credentials:
        msg = "a remote SMTP host needs EMAIL_SECURITY, EMAIL_USERNAME, EMAIL_PASSWORD"
        raise EmailMisconfiguredError(msg)
    return SmtpEmailSender(
        host=host,
        port=port,
        security=settings.security,
        username=settings.username,
        password=settings.password,
        from_addr=from_addr,
        public_base_url=base,
        timeout=settings.timeout,
    )


class SmtpEmailSender:
    """Sends letters through an SMTP provider."""

    def __init__(  # ruff: ignore[too-many-arguments] -- every setting of the provider
        self,
        *,
        host: str,
        port: int,
        security: EmailSecurity | None,
        username: str | None,
        password: SecretStr | None,
        from_addr: str,
        public_base_url: str,
        timeout: float,
    ) -> None:
        self._host: str = host
        self._port: int = port
        self._security: EmailSecurity | None = security
        self._username: str | None = username
        self._password: SecretStr | None = password
        self._from_addr: str = from_addr
        self._base: str = public_base_url.rstrip("/")
        self._timeout: float = timeout

    async def send_verification(self, email: str, token: str) -> None:
        """Send the letter that confirms an address.

        Args:
            email: str - Recipient.
            token: str - Raw token; it goes into the letter, never into the log.

        """
        link = f"{self._base}{_VERIFY_PATH}?token={token}"
        subject, html, text = render_verification_email(link)
        await self._deliver(email, subject, html, text)
        _log.info("verification_email_sent", email=email)

    async def send_password_reset(self, email: str, token: str) -> None:
        """Send the letter with a reset link.

        Args:
            email: str - Recipient.
            token: str - Raw token; it goes into the letter, never into the log.

        """
        link = f"{self._base}{_RESET_PATH}?token={token}"
        subject, html, text = render_password_reset_email(link)
        await self._deliver(email, subject, html, text)
        _log.info("password_reset_email_sent", email=email)

    async def _deliver(self, email: str, subject: str, html: str, text: str) -> None:
        """Send a letter and sort a refusal into permanent or transient.

        A permanent refusal is not retried; a transient one is left to the
        relay backoff. A wrong password or `From` is transient at any code:
        it is fixed in the settings, and the letter should survive until then.

        Args:
            email: str - Recipient.
            subject: str - Subject.
            html: str - HTML part.
            text: str - Plain text part.

        Raises:
            EmailPermanentlyUndeliverableError: If the provider refused with a 5xx
                content or recipient code.
            SMTPRecipientsRefused: If a recipient was refused only for now.
            SMTPAuthenticationError: If the login was refused.
            SMTPSenderRefused: If the `From` address was refused.
            SMTPResponseException: If the provider refused for now.

        """
        message = EmailMessage()
        message["From"] = self._from_addr
        message["To"] = email
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        password = None if self._password is None else self._password.get_secret_value()
        try:
            _ = await aiosmtplib.send(
                message,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=password,
                use_tls=self._security is EmailSecurity.SSL,
                start_tls=self._security is EmailSecurity.STARTTLS,
                timeout=self._timeout,
            )
        except SMTPRecipientsRefused as exc:
            # Permanent only if every recipient got a 5xx; a greylisting 450 is not.
            if all(r.code // 100 == _PERMANENT_CLASS for r in exc.recipients):
                msg = f"smtp refused recipient {email}"
                raise EmailPermanentlyUndeliverableError(msg) from exc
            raise
        except (SMTPAuthenticationError, SMTPSenderRefused):
            raise
        except SMTPResponseException as exc:
            if exc.code // 100 == _PERMANENT_CLASS:
                msg = f"smtp permanent {exc.code} for {email}"
                raise EmailPermanentlyUndeliverableError(msg) from exc
            raise
