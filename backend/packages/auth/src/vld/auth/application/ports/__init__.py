"""Ports of the auth domain, one module per port."""

from __future__ import annotations

from ._clock import Clock
from ._email_sender import EmailPermanentlyUndeliverableError, EmailSender
from ._outbox import Outbox
from ._password_hasher import PasswordHasher

__all__ = (
    "Clock",
    "EmailPermanentlyUndeliverableError",
    "EmailSender",
    "Outbox",
    "PasswordHasher",
)
