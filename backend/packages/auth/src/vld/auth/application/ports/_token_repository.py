"""Port of the one-time token store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from vld.auth.domain import TokenPurpose, VerificationToken


class TokenRepository(Protocol):
    """Store of one-time tokens."""

    async def add(self, token: VerificationToken) -> None:
        """Store an issued token.

        Args:
            token: VerificationToken - The token.

        """
        ...

    async def get_by_hash(
        self,
        token_hash: str,
        purpose: TokenPurpose,
    ) -> VerificationToken | None:
        """Find a token by the hash of its value and its purpose.

        Args:
            token_hash: str - Hash of the value.
            purpose: TokenPurpose - Purpose the token is looked up for.

        Returns:
            VerificationToken | None - The token, or None.

        """
        ...

    async def consume_outstanding(
        self,
        user_id: uuid.UUID,
        purpose: TokenPurpose,
        *,
        now: datetime,
    ) -> None:
        """Use up every unused token of an account with this purpose.

        Args:
            user_id: uuid.UUID - Owner of the tokens.
            purpose: TokenPurpose - Purpose whose tokens are used up.
            now: datetime - Moment of use.

        """
        ...

    async def update(self, token: VerificationToken) -> None:
        """Mark a token used unless someone did it first.

        Args:
            token: VerificationToken - The token.

        Raises:
            TokenAlreadyUsedError: If another request used the row first.
            EntityNotFoundError: If the token was never stored or its row is gone.

        """
        ...
