"""Describing the logged-in user."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field read at runtime
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vld.auth.domain import EntityNotFoundError

if TYPE_CHECKING:
    from vld.auth.application.ports import UserRepository
    from vld.auth.domain import Profile, Role


@dataclass(frozen=True, slots=True)
class MeView:
    """The logged-in user as the site shows them.

    Attributes:
        user_id: uuid.UUID - Account.
        email: str - Address.
        email_verified: bool - Whether the address is confirmed.
        role: Role - Role.
        is_admin: bool - Admin rights.
        profile: Profile - Personal details.

    """

    user_id: uuid.UUID
    email: str
    email_verified: bool
    role: Role
    is_admin: bool
    profile: Profile


class DescribeMe:
    """Describe the logged-in user."""

    def __init__(self, users: UserRepository) -> None:
        self._users: UserRepository = users

    async def __call__(self, user_id: uuid.UUID) -> MeView:
        """Describe the logged-in user.

        Args:
            user_id: uuid.UUID - Account from the verified token.

        Returns:
            MeView - The description.

        Raises:
            EntityNotFoundError: If the account row is gone.

        """
        user = await self._users.get_by_id(user_id)
        if user is None:
            msg = f"user {user_id} does not exist"
            raise EntityNotFoundError(msg)
        return MeView(
            user_id=user.id,
            email=user.email,
            email_verified=user.email_verified,
            role=user.role,
            is_admin=user.is_admin,
            profile=user.profile,
        )
