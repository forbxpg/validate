"""The `AuthApi` contract over the account store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import UserRepository
    from vld.auth.domain import Role


class AuthApiAdapter:
    """Answers the neighbours about an account."""

    def __init__(self, users: UserRepository) -> None:
        self._users: UserRepository = users

    async def role_of(self, user_id: uuid.UUID) -> Role | None:
        """Tell the role of an active account.

        Args:
            user_id: uuid.UUID - Account id.

        Returns:
            Role | None - The role, or None if the account is gone or turned off.

        """
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return user.role
