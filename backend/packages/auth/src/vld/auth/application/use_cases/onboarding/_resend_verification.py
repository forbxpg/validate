"""Sending the confirmation letter again."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import email_bucket_key
from vld.auth.domain import USER_REGISTERED_EVENT, DomainEvent

if TYPE_CHECKING:
    from vld.auth.application.ports import Outbox, RateLimiter, UserRepository
    from vld.core.database import UnitOfWork

# Each request mails someone: a few per hour is enough for a lost letter.
_EMAIL_LIMIT = 3
_EMAIL_WINDOW_MS = 60 * 60_000


@dataclass(frozen=True, slots=True)
class ResendVerificationCommand:
    """A request for another confirmation letter.

    Attributes:
        email: str - Address as typed.

    """

    email: str


class ResendVerification:
    """Record another confirmation letter, revealing nothing about the account."""

    def __init__(
        self,
        users: UserRepository,
        outbox: Outbox,
        limiter: RateLimiter,
        uow: UnitOfWork,
    ) -> None:
        self._users: UserRepository = users
        self._outbox: Outbox = outbox
        self._limiter: RateLimiter = limiter
        self._uow: UnitOfWork = uow

    async def __call__(self, command: ResendVerificationCommand) -> None:
        """Ask for the letter again if there is someone to confirm.

        Args:
            command: ResendVerificationCommand - The request.

        """
        # The bucket does not depend on the account: the answer reveals nothing.
        await self._limiter.hit(
            email_bucket_key("resend_verification", command.email),
            _EMAIL_LIMIT,
            _EMAIL_WINDOW_MS,
        )
        async with self._uow:
            user = await self._users.get_by_email(command.email)
            if user is None or user.email_verified:
                return
            await self._outbox.add(
                [DomainEvent(USER_REGISTERED_EVENT, {"user_id": str(user.id)})],
            )
            await self._uow.commit()
