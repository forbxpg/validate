"""Turning an account off and back on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import AuthAuditAction, UserNotFoundError
from vld.core.audit import AuditEntry

from ._target_guard import guard_target

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import Clock, UserRepository
    from vld.auth.domain import User
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


class SetUserActive:
    """Turn an account off, which ends its sessions, or back on."""

    def __init__(
        self,
        users: UserRepository,
        clock: Clock,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> None:
        self._users: UserRepository = users
        self._clock: Clock = clock
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit

    async def __call__(
        self,
        target_id: uuid.UUID,
        *,
        active: bool,
        actor_id: uuid.UUID | None,
    ) -> User:
        """Set whether the account may log in.

        Args:
            target_id: uuid.UUID - Account to change.
            active: bool - True to turn it on, False to turn it off.
            actor_id: uuid.UUID | None - Admin acting through the site, or None
                from the console, where no guard applies.

        Returns:
            User - The account after the change.

        Raises:
            UserNotFoundError: If the account does not exist.

        """
        async with self._uow:
            user = await self._users.get_by_id(target_id)
            if user is None:
                msg = f"user {target_id} does not exist"
                raise UserNotFoundError(msg)
            if actor_id is not None:
                guard_target(actor_id, user)
            if active:
                user.activate()
            else:
                user.deactivate(self._clock.now())
            await self._users.update(user)
            await self._audit.record(
                AuditEntry(
                    action=(
                        AuthAuditAction.USER_ACTIVATED
                        if active
                        else AuthAuditAction.USER_DEACTIVATED
                    ),
                    actor_id=actor_id,
                    target_id=target_id,
                ),
            )
            await self._uow.commit()
        return user
