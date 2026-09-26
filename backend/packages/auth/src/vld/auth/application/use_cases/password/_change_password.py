"""Changing the password while logged in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import TokenPair, check_password
from vld.auth.domain import EntityNotFoundError, InvalidCredentialsError
from vld.core.audit import AuditAction, AuditEntry

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import (
        Clock,
        PasswordHasher,
        TokenIssuer,
        UserRepository,
    )
    from vld.auth.config import PasswordSettings
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


@dataclass(frozen=True, slots=True)
class ChangePasswordCommand:
    """A password change.

    Attributes:
        user_id: uuid.UUID - Account of the logged-in user.
        current_password: str - Password the user has now.
        new_password: str - Password to set.

    """

    user_id: uuid.UUID
    current_password: str
    new_password: str


class ChangePassword:
    """Check the current password, set a new one and keep this device logged in."""

    def __init__(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        issuer: TokenIssuer,
        clock: Clock,
        uow: UnitOfWork,
        audit: AuditLog,
        settings: PasswordSettings,
    ) -> None:
        self._users: UserRepository = users
        self._hasher: PasswordHasher = hasher
        self._issuer: TokenIssuer = issuer
        self._clock: Clock = clock
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._settings: PasswordSettings = settings

    async def __call__(self, command: ChangePasswordCommand) -> TokenPair:
        """Change the password.

        Every session ends with the change, a stolen refresh token included; the
        device that asked gets a new pair so the user stays logged in there.

        Args:
            command: ChangePasswordCommand - The change.

        Returns:
            TokenPair - New tokens for the device that asked.

        Raises:
            EntityNotFoundError: If the account does not exist.
            InvalidCredentialsError: If the current password does not match.

        """
        check_password(command.new_password, self._settings)
        async with self._uow:
            user = await self._users.get_by_id(command.user_id)
        if user is None:
            msg = f"user {command.user_id} does not exist"
            raise EntityNotFoundError(msg)
        if not await self._hasher.verify(command.current_password, user.password_hash):
            msg = "current password does not match"
            raise InvalidCredentialsError(msg)
        password_hash = await self._hasher.hash(command.new_password)

        async with self._uow:
            user.set_password(password_hash, now=self._clock.now())
            await self._users.update(user)
            await self._audit.record(
                AuditEntry(action=AuditAction.PASSWORD_CHANGED, actor_id=user.id),
            )
            await self._uow.commit()
        access, refresh = self._issuer.issue_pair(
            user.id,
            not_before=user.tokens_invalidated_after,
        )
        return TokenPair(access=access, refresh=refresh)
