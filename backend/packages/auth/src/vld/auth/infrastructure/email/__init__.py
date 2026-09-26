"""Sending letters: the SMTP and console senders and the letter content."""

from __future__ import annotations

from ._console import ConsoleEmailSender, ConsoleEmailSenderInProductionError
from ._content import render_password_reset_email, render_verification_email

__all__ = (
    "ConsoleEmailSender",
    "ConsoleEmailSenderInProductionError",
    "render_password_reset_email",
    "render_verification_email",
)
