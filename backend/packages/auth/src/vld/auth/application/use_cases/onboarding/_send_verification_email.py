"""Handler of `auth.user_registered`: the confirmation letter."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import (
    derive_verification_token,
    hash_token,
    issue_verification,
)
from vld.auth.domain import TokenPurpose

if TYPE_CHECKING:
    from vld.auth.application.ports import (
        Clock,
        EmailSender,
        TokenRepository,
        UserRepository,
    )
    from vld.auth.config import JwtSettings
    from vld.auth.domain import DomainEvent


class UnknownRegisteredUserError(RuntimeError):
    """The event names an account that no longer exists."""


class SendVerificationEmail:
    """Issue a confirmation token and send the letter."""

    def __init__(
        self,
        users: UserRepository,
        tokens: TokenRepository,
        email: EmailSender,
        clock: Clock,
        settings: JwtSettings,
    ) -> None:
        self._users: UserRepository = users
        self._tokens: TokenRepository = tokens
        self._email: EmailSender = email
        self._clock: Clock = clock
        self._settings: JwtSettings = settings

    async def prepare(self, event: DomainEvent, delivery_id: int) -> tuple[str, str]:
        """Issue the token and tell whom to send what.

        The token is derived from the outbox row, so a retried delivery stores
        nothing new and sends the same link.

        Args:
            event: DomainEvent - `auth.user_registered` with `user_id`.
            delivery_id: int - Id of the outbox row.

        Returns:
            tuple[str, str] - Recipient and raw token for the link.

        Raises:
            UnknownRegisteredUserError: If the account is gone.

        """
        user_id = uuid.UUID(event.payload["user_id"])
        user = await self._users.get_by_id(user_id)
        if user is None:
            msg = f"user {user_id} has no address to verify"
            raise UnknownRegisteredUserError(msg)
        raw_token = derive_verification_token(
            self._settings.secret_key.get_secret_value(),
            delivery_id,
        )
        existing = await self._tokens.get_by_hash(
            hash_token(raw_token),
            TokenPurpose.EMAIL_VERIFY,
        )
        if existing is None:
            _, token = issue_verification(
                user.id,
                self._clock.now(),
                raw_token=raw_token,
            )
            await self._tokens.add(token)
        return user.email, raw_token

    async def deliver(self, recipient: str, raw_token: str) -> None:
        """Send the confirmation letter.

        Args:
            recipient: str - Recipient.
            raw_token: str - Raw token for the link.

        """
        await self._email.send_verification(recipient, raw_token)
