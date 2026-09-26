"""The tasks the worker runs from the broker: sending the letter of an outbox row."""

from __future__ import annotations

from ._delivery import send_email, send_letter
from ._handlers import EventHandler, handler_type
from ._tasks import SEND_EMAIL_TASK, EmailPublisher, register

__all__ = (
    "SEND_EMAIL_TASK",
    "EmailPublisher",
    "EventHandler",
    "handler_type",
    "register",
    "send_email",
    "send_letter",
)
