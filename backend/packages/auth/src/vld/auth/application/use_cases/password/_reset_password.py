"""Setting a password through a link from a letter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import (
    InvalidTokenError,
    check_password,
    hash_token,
)
from vld.auth.domain import AuthAuditAction, TokenPurpose
from vld.core.audit import AuditEntry

if TYPE_CHECKING:
    from vld.auth.application.ports import (
        Clock,
        PasswordHasher,
        TokenRepository,
        UserRepository,
    )
    from vld.auth.config import PasswordSettings
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


class ResetPassword:
    """Use up a reset token, set the password and confirm the address."""

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        *,
        users: UserRepository,
        tokens: TokenRepository,
        hasher: PasswordHasher,
        clock: Clock,
        uow: UnitOfWork,
        audit: AuditLog,
        settings: PasswordSettings,
    ) -> None:
        self._users: UserRepository = users
        self._tokens: TokenRepository = tokens
        self._hasher: PasswordHasher = hasher
        self._clock: Clock = clock
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._settings: PasswordSettings = settings

    async def __call__(self, raw_token: str, password: str) -> None:
        """Set a new password with the token from the letter and end every session.

        Args:
            raw_token: str - Token from the link.
            password: str - New plain password.

        Raises:
            InvalidTokenError: If the token is unknown or has another purpose.

        """
        check_password(password, self._settings)
        # Before the transaction: hashing is slow; the IP bucket guards bad tokens.
        password_hash = await self._hasher.hash(password)

        async with self._uow:
            token = await self._tokens.get_by_hash(
                hash_token(raw_token),
                TokenPurpose.PASSWORD_RESET,
            )
            if token is None:
                msg = "password reset token not found"
                raise InvalidTokenError(msg)
            user = await self._users.get_by_id(token.user_id)
            if user is None:
                msg = "token owner not found"
                raise InvalidTokenError(msg)
            now = self._clock.now()
            token.consume(now=now)
            await self._tokens.update(token)
            user.reset_password(password_hash, now=now)
            await self._users.update(user)
            await self._audit.record(
                AuditEntry(action=AuthAuditAction.PASSWORD_RESET, actor_id=user.id),
            )
            await self._uow.commit()
