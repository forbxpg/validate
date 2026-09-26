"""Asking for a reset letter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import email_bucket_key
from vld.auth.domain import PASSWORD_RESET_REQUESTED_EVENT, DomainEvent

if TYPE_CHECKING:
    from vld.auth.application.ports import Outbox, RateLimiter, UserRepository
    from vld.core.database import UnitOfWork

# Each request mails someone: without a bucket the form sends letters to anyone.
_EMAIL_LIMIT = 3
_EMAIL_WINDOW_MS = 60 * 60_000


class RequestPasswordReset:
    """Record a reset letter without revealing whether the account exists."""

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

    async def __call__(self, email: str) -> None:
        """Ask for a reset letter if the address has an account.

        Args:
            email: str - Address typed in the "forgot password" form.

        """
        await self._limiter.hit(
            email_bucket_key("password_reset", email),
            _EMAIL_LIMIT,
            _EMAIL_WINDOW_MS,
        )
        async with self._uow:
            user = await self._users.get_by_email(email)
            if user is None:
                return
            # Only the id: a raw token in the outbox would lie there in plain text.
            await self._outbox.add(
                [
                    DomainEvent(
                        PASSWORD_RESET_REQUESTED_EVENT,
                        {"user_id": str(user.id)},
                    ),
                ],
            )
            await self._uow.commit()
