"""Identity of the token presenter and the port of its establishment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class Identity:
    """Who sent the request.

    Attributes:
        user_id: uuid.UUID - Owner of the presented token.
        role: str - Business role, exactly one.
        is_admin: bool - Administrative rights.

    """

    user_id: uuid.UUID
    role: str
    is_admin: bool


class IdentityProvider(Protocol):
    """Establishing identity by presented access token."""

    async def identify(self, token: str) -> Identity:
        """Check the token and return to whom it belongs.

        Args:
            token: str - Presented access token.

        Returns:
            Identity - Owner of the token, its role and admin flag.

        Raises:
            Exception: A domain error when the token is refused.

        """
        ...
