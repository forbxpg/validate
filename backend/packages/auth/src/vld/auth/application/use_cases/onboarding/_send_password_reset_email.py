"""Handler of `auth.password_reset_requested`: the letter with a reset link."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import (
    derive_password_reset_token,
    hash_token,
    issue_password_reset,
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


class UnknownResetTargetError(RuntimeError):
    """The event names an account that no longer exists."""


class SendPasswordResetEmail:
    """Issue a reset token and send the letter."""

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
        """Issue the reset token and tell whom to send what.

        Older reset links of the account stop working: only the newest is valid.

        Args:
            event: DomainEvent - `auth.password_reset_requested` with `user_id`.
            delivery_id: int - Id of the outbox row.

        Returns:
            tuple[str, str] - Recipient and raw token for the link.

        Raises:
            UnknownResetTargetError: If the account is gone.

        """
        user_id = uuid.UUID(event.payload["user_id"])
        user = await self._users.get_by_id(user_id)
        if user is None:
            msg = f"user {user_id} has no address to send a reset link to"
            raise UnknownResetTargetError(msg)
        raw_token = derive_password_reset_token(
            self._settings.secret_key.get_secret_value(),
            delivery_id,
        )
        existing = await self._tokens.get_by_hash(
            hash_token(raw_token),
            TokenPurpose.PASSWORD_RESET,
        )
        if existing is None:
            now = self._clock.now()
            # Before the insert: add() flushes, and the UPDATE would hit the new token.
            await self._tokens.consume_outstanding(
                user.id,
                TokenPurpose.PASSWORD_RESET,
                now=now,
            )
            _, token = issue_password_reset(user.id, now, raw_token=raw_token)
            await self._tokens.add(token)
        return user.email, raw_token

    async def deliver(self, recipient: str, raw_token: str) -> None:
        """Send the letter with the reset link.

        Args:
            recipient: str - Recipient.
            raw_token: str - Raw token for the link.

        """
        await self._email.send_password_reset(recipient, raw_token)
