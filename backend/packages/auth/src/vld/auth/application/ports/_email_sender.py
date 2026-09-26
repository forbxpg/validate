"""Port of sending letters."""

from __future__ import annotations

from typing import Protocol


class EmailPermanentlyUndeliverableError(RuntimeError):
    """The letter can never be delivered; do not retry it."""


class EmailSender(Protocol):
    """Sending letters with links."""

    async def send_verification(self, email: str, token: str) -> None:
        """Send the link that confirms an address.

        Args:
            email: str - Recipient.
            token: str - Raw token; only its hash is stored.

        """
        ...

    async def send_password_reset(self, email: str, token: str) -> None:
        """Send the link that sets a new password.

        Args:
            email: str - Recipient.
            token: str - Raw token; only its hash is stored.

        """
        ...
