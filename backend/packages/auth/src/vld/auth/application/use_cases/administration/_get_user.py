"""An account card for the admin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import UserNotFoundError

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import UserRepository
    from vld.auth.domain import User


class GetUser:
    """Return an account by id."""

    def __init__(self, users: UserRepository) -> None:
        self._users: UserRepository = users

    async def __call__(self, user_id: uuid.UUID) -> User:
        """Find an account.

        Args:
            user_id: uuid.UUID - Id given by the admin.

        Returns:
            User - The account.

        Raises:
            UserNotFoundError: If the account does not exist.

        """
        user = await self._users.get_by_id(user_id)
        if user is None:
            msg = f"user {user_id} does not exist"
            raise UserNotFoundError(msg)
        return user
