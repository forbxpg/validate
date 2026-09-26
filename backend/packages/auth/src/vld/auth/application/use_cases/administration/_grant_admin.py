"""Granting admin rights from the console."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import AuthAuditAction, UserNotFoundError
from vld.core.audit import AuditEntry

if TYPE_CHECKING:
    from vld.auth.application.ports import UserRepository
    from vld.auth.domain import User
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


class GrantAdmin:
    """Give admin rights to an existing account."""

    def __init__(self, users: UserRepository, uow: UnitOfWork, audit: AuditLog) -> None:
        self._users: UserRepository = users
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit

    async def __call__(self, email: str) -> User:
        """Make the account of an address an admin.

        Args:
            email: str - Address of a registered account.

        Returns:
            User - The account, now an admin.

        Raises:
            UserNotFoundError: If no account has the address.

        """
        async with self._uow:
            user = await self._users.get_by_email(email)
            if user is None:
                msg = f"no account has the address {email}"
                raise UserNotFoundError(msg)
            if user.is_admin:
                return user
            user.grant_admin()
            await self._users.update(user)
            await self._audit.record(
                AuditEntry(action=AuthAuditAction.ADMIN_GRANTED, target_id=user.id),
            )
            await self._uow.commit()
        return user
