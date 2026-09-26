"""Changing the role of an account."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import UserNotFoundError
from vld.core.audit import AuditAction, AuditEntry

from ._target_guard import guard_target

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import UserRepository
    from vld.auth.domain import Role, User
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


class ChangeUserRole:
    """Set another role on an account."""

    def __init__(self, users: UserRepository, uow: UnitOfWork, audit: AuditLog) -> None:
        self._users: UserRepository = users
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit

    async def __call__(
        self,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
        role: Role,
    ) -> User:
        """Change the role.

        Args:
            actor_id: uuid.UUID - Admin acting.
            target_id: uuid.UUID - Account to change.
            role: Role - New role.

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
            guard_target(actor_id, user)
            previous = user.role
            if previous is role:
                return user
            user.change_role(role)
            await self._users.update(user)
            await self._audit.record(
                AuditEntry(
                    action=AuditAction.USER_ROLE_CHANGED,
                    actor_id=actor_id,
                    target_id=target_id,
                    payload={"from": str(previous), "to": str(role)},
                ),
            )
            await self._uow.commit()
        return user
