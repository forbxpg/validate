"""Deleting an account from the console."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import UserNotFoundError
from vld.core.audit import AuditAction, AuditEntry

if TYPE_CHECKING:
    from vld.auth.application.ports import UserRepository
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


class DeleteUser:
    """Delete an account with its tokens, at the user's request."""

    def __init__(self, users: UserRepository, uow: UnitOfWork, audit: AuditLog) -> None:
        self._users: UserRepository = users
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit

    async def __call__(self, email: str) -> None:
        """Delete the account of an address.

        The audit log keeps only the id: the personal data leaves with the row.

        Args:
            email: str - Address of the account.

        Raises:
            UserNotFoundError: If no account has the address.

        """
        async with self._uow:
            user = await self._users.get_by_email(email)
            if user is None:
                msg = f"no account has the address {email}"
                raise UserNotFoundError(msg)
            _ = await self._users.delete(user.id)
            await self._audit.record(
                AuditEntry(action=AuditAction.USER_DELETED, target_id=user.id),
            )
            await self._uow.commit()
