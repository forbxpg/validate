"""Read contract of the auth domain: what the neighbours ask about an account."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid

    from vld.auth.domain import Role


class AuthApi(Protocol):
    """Questions the other domains ask about an account."""

    async def role_of(self, user_id: uuid.UUID) -> Role | None:
        """Tell the role of an active account.

        Args:
            user_id: uuid.UUID - Account id, kept by other domains without a FK.

        Returns:
            Role | None - The role, or None if the account is gone or turned off.

        """
        ...
