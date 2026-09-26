"""Ending every session of an account."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import EntityNotFoundError
from vld.core.audit import AuditAction, AuditEntry

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import Clock, UserRepository
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


class InvalidateSessions:
    """Void every token of an account: logout everywhere, or an admin's reset."""

    def __init__(
        self,
        users: UserRepository,
        clock: Clock,
        audit: AuditLog,
        uow: UnitOfWork,
    ) -> None:
        self._users: UserRepository = users
        self._clock: Clock = clock
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow

    async def __call__(self, user_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """Void every token of an account.

        Args:
            user_id: uuid.UUID - Account whose tokens are voided.
            actor_id: uuid.UUID - The owner, or the admin who asked.

        Raises:
            EntityNotFoundError: If the account does not exist.

        """
        async with self._uow:
            user = await self._users.get_by_id(user_id)
            if user is None:
                msg = f"user {user_id} does not exist"
                raise EntityNotFoundError(msg)
            user.invalidate_tokens(self._clock.now())
            await self._users.update(user)
            await self._audit.record(
                AuditEntry(
                    action=AuditAction.SESSIONS_INVALIDATED,
                    actor_id=actor_id,
                    target_id=user_id,
                ),
            )
            await self._uow.commit()
