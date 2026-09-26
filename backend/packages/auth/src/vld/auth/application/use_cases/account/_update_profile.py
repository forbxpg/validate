"""Changing the own profile."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import EntityNotFoundError

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import UserRepository
    from vld.auth.domain import Profile
    from vld.core.database import UnitOfWork


class UpdateProfile:
    """Replace the personal details of the logged-in user."""

    def __init__(self, users: UserRepository, uow: UnitOfWork) -> None:
        self._users: UserRepository = users
        self._uow: UnitOfWork = uow

    async def __call__(self, user_id: uuid.UUID, profile: Profile) -> Profile:
        """Replace the profile.

        Args:
            user_id: uuid.UUID - Account from the verified token.
            profile: Profile - New details.

        Returns:
            Profile - The stored details.

        Raises:
            EntityNotFoundError: If the account row is gone.

        """
        async with self._uow:
            user = await self._users.get_by_id(user_id)
            if user is None:
                msg = f"user {user_id} does not exist"
                raise EntityNotFoundError(msg)
            user.update_profile(profile)
            await self._users.update(user)
            await self._uow.commit()
        return user.profile
