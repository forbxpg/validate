"""A page of accounts for the admin."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vld.auth.application.ports import UserRepository, UsersPage
    from vld.auth.domain import Role


class ListUsers:
    """Return a page of accounts by filters."""

    def __init__(self, users: UserRepository) -> None:
        self._users: UserRepository = users

    async def __call__(
        self,
        *,
        role: Role | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> UsersPage:
        """Select a page of accounts.

        Args:
            role: Role | None - Role, or None for any.
            is_active: bool | None - Access state, or None for any.
            limit: int - Page size; the HTTP layer bounds it.
            offset: int - Accounts to skip.

        Returns:
            UsersPage - The page and the number of matching accounts.

        """
        return await self._users.search(
            role=role,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
