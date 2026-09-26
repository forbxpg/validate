"""SMTP sender: the links, the sorting of refusals, no token in the logs."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import aiosmtplib
import pytest
from aiosmtplib import (
    SMTPAuthenticationError,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPSenderRefused,
)
from aiosmtplib.errors import SMTPRecipientRefused
from pydantic import SecretStr
from structlog.testing import capture_logs

from vld.auth.application import EmailPermanentlyUndeliverableError
from vld.auth.config import EmailSecurity, EmailSettings
from vld.auth.infrastructure.email import (
    EmailMisconfiguredError,
    SmtpEmailSender,
    build_smtp_sender,
)

if TYPE_CHECKING:
    from email.message import EmailMessage

_BASE = "https://validate.example"
_TOKEN = "raw-secret-token-xyz"
_SEND = "vld.auth.infrastructure.email._smtp.aiosmtplib.send"


def _sender() -> SmtpEmailSender:
    return SmtpEmailSender(
        host="smtp.example.org",
        port=465,
        security=EmailSecurity.SSL,
        username="bot@validate.example",
        password=SecretStr("pw"),
        from_addr="no-reply@validate.example",
        public_base_url=f"{_BASE}/",
        timeout=10.0,
    )


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Catch the letters instead of sending them."""
    box: list[EmailMessage] = []

    async def _fake_send(message: EmailMessage, **kwargs: object) -> None:
        del kwargs
        box.append(message)

    monkeypatch.setattr(aiosmtplib, "send", _fake_send)
    return box


def _body(message: EmailMessage) -> str:
    parts: list[str] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        parts.append(str(cast("object", part.get_content())))
    return "".join(parts)


async def test_reset_link_points_at_the_new_password_page(
    captured: list[EmailMessage],
) -> None:
    """The reset link leads to the page of the new password."""
    await _sender().send_password_reset("lost@b.co", _TOKEN)

    [message] = captured
    body = _body(message)
    assert f"{_BASE}/auth/password/new?token={_TOKEN}" in body
    assert "пароль останется прежним" in body


async def test_verification_link_points_at_the_confirmation_page(
    captured: list[EmailMessage],
) -> None:
    """The confirmation link leads to its own page, with its own text."""
    await _sender().send_verification("new@b.co", _TOKEN)

    [message] = captured
    body = _body(message)
    assert f"{_BASE}/auth/verify-email?token={_TOKEN}" in body
    assert "/auth/password/new" not in body
    assert message["From"] == "no-reply@validate.example"
    assert message["To"] == "new@b.co"


@pytest.mark.parametrize(
    "refusal",
    [
        SMTPResponseException(550, "no such mailbox"),
        SMTPRecipientsRefused([SMTPRecipientRefused(550, "no mailbox", "x@b.co")]),
    ],
    ids=["5xx", "5xx-recipient"],
)
async def test_a_5xx_about_the_letter_is_permanent(refusal: Exception) -> None:
    """A hard bounce is not retried: the relay fails the row."""
    with (
        patch(_SEND, side_effect=refusal),
        pytest.raises(EmailPermanentlyUndeliverableError),
    ):
        await _sender().send_verification("x@b.co", _TOKEN)


@pytest.mark.parametrize(
    "refusal",
    [
        SMTPResponseException(451, "try later"),
        SMTPRecipientsRefused([SMTPRecipientRefused(450, "greylisted", "x@b.co")]),
        SMTPSenderRefused(450, "try later", "no-reply@validate.example"),
        SMTPSenderRefused(550, "sender rejected", "no-reply@validate.example"),
        SMTPAuthenticationError(535, "auth failed"),
    ],
    ids=["4xx", "4xx-recipient", "4xx-sender", "5xx-sender", "auth"],
)
async def test_a_refusal_fixed_in_time_or_in_settings_is_transient(
    refusal: Exception,
) -> None:
    """Greylisting, a wrong login or `From` keep the letter for a retry."""
    with patch(_SEND, side_effect=refusal), pytest.raises(type(refusal)):
        await _sender().send_verification("x@b.co", _TOKEN)


async def test_timeout_is_forwarded() -> None:
    """A hung connection cannot hang the worker."""
    with patch(_SEND) as send:
        await _sender().send_verification("x@b.co", _TOKEN)

    assert send.call_args.kwargs["timeout"] == pytest.approx(10.0)


async def test_token_not_logged() -> None:
    """Access to the logs must not hand out accounts."""
    with capture_logs() as logs, patch(_SEND) as send:
        await _sender().send_verification("x@b.co", _TOKEN)

    assert send.await_count == 1
    assert all(_TOKEN not in str(entry) for entry in logs)


def test_local_mailpit_accepts_plain_smtp_without_login() -> None:
    """The local catcher needs neither a login nor TLS."""
    settings = EmailSettings(
        host="127.0.0.1",
        port=1025,
        from_addr="noreply@validate.local",
        public_base_url="http://localhost:5173",
    )

    sender = build_smtp_sender(settings)

    assert sender._username is None
    assert sender._security is None


@pytest.mark.parametrize(
    "settings",
    [
        EmailSettings(host="smtp.example.org"),
        EmailSettings(
            host="smtp.example.org",
            port=465,
            from_addr="no-reply@validate.example",
            public_base_url=_BASE,
        ),
    ],
    ids=["no-port-or-sender", "remote-without-login"],
)
def test_partial_settings_fail_at_startup(settings: EmailSettings) -> None:
    """A host with incomplete settings is a loud refusal, not a silent outbox."""
    with pytest.raises(EmailMisconfiguredError):
        _ = build_smtp_sender(settings)
