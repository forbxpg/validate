"""Port of the account store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid

    from vld.auth.domain import Role, User


@dataclass(frozen=True, slots=True)
class UsersPage:
    """One page of accounts.

    Attributes:
        users: list[User] - Accounts of the page, oldest first.
        total: int - Accounts matching the filter, without the page.

    """

    users: list[User]
    total: int


class UserRepository(Protocol):
    """Store of accounts."""

    async def search(
        self,
        *,
        role: Role | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> UsersPage:
        """Select a page of accounts by filters.

        Args:
            role: Role | None - Role, or None for any.
            is_active: bool | None - Access state, or None for any.
            limit: int - Page size, positive.
            offset: int - Accounts to skip, non-negative.

        Returns:
            UsersPage - The page and the number of matching accounts.

        """
        ...

    async def add(self, user: User) -> None:
        """Store a new account.

        Args:
            user: User - The account.

        Raises:
            EmailAlreadyTakenError: If the address is taken.

        """
        ...

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Find an account by id.

        Args:
            user_id: uuid.UUID - The id.

        Returns:
            User | None - The account, or None.

        """
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Find an account by address, ignoring case and surrounding spaces.

        Args:
            email: str - The address.

        Returns:
            User | None - The account, or None.

        """
        ...

    async def update_password_hash(
        self,
        user_id: uuid.UUID,
        expected_hash: str,
        new_hash: str,
    ) -> bool:
        """Replace the password hash only if it is still the expected one.

        Args:
            user_id: uuid.UUID - Owner.
            expected_hash: str - Hash the use case has just checked.
            new_hash: str - New hash.

        Returns:
            bool - True if the row was updated.

        """
        ...

    async def update(self, user: User) -> None:
        """Save the changes of an account.

        Args:
            user: User - The account.

        Raises:
            EntityNotFoundError: If the account is not stored.

        """
        ...

    async def delete(self, user_id: uuid.UUID) -> bool:
        """Delete an account with everything that belongs to it.

        Args:
            user_id: uuid.UUID - The account.

        Returns:
            bool - True if a row was deleted.

        """
        ...
