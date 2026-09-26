"""Sending letters: the SMTP and console senders and the letter content."""

from __future__ import annotations

from ._console import ConsoleEmailSender, ConsoleEmailSenderInProductionError
from ._content import render_password_reset_email, render_verification_email
from ._smtp import EmailMisconfiguredError, SmtpEmailSender, build_smtp_sender

__all__ = (
    "ConsoleEmailSender",
    "ConsoleEmailSenderInProductionError",
    "EmailMisconfiguredError",
    "SmtpEmailSender",
    "build_smtp_sender",
    "render_password_reset_email",
    "render_verification_email",
)
