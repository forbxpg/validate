"""Letters written to the log instead of sent, for the local stand and tests."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from vld.core.config import AppSettings

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


class ConsoleEmailSenderInProductionError(RuntimeError):
    """The console sender was built in production."""


def _show(event: str, **fields: str) -> None:
    """Write a letter to the log and to the process stdout.

    Args:
        event: str - Name of the letter.
        **fields: str - Fields to see in the terminal.

    """
    _log.info(event, **fields)
    rendered = " ".join(f"{name}={value}" for name, value in fields.items())
    print(f"{event} {rendered}", file=sys.stdout, flush=True)  # ruff: ignore[print] -- the terminal is where the local stand reads the link


class ConsoleEmailSender:
    """Writes the link of a letter to the log.

    Raises:
        ConsoleEmailSenderInProductionError: On construction in production,
            where the log would leak working links.

    """

    def __init__(self, app: AppSettings) -> None:
        if app.env == "production":
            msg = (
                "the console sender writes working links to the log; "
                "set EMAIL_HOST, or APP_ENV=local|test outside production"
            )
            raise ConsoleEmailSenderInProductionError(msg)

    @classmethod
    async def send_verification(cls, email: str, token: str) -> None:
        """Show the confirmation link in the log.

        Args:
            email: str - Recipient.
            token: str - Raw token.

        """
        _show("verification_email", email=email, token=token)

    @classmethod
    async def send_password_reset(cls, email: str, token: str) -> None:
        """Show the reset link in the log.

        Args:
            email: str - Recipient.
            token: str - Raw token.

        """
        _show("password_reset_email", email=email, token=token)
