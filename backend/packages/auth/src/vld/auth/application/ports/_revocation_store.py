"""Port of the revocation list."""

from __future__ import annotations

from typing import Protocol

from vld.auth.domain import AuthDomainError


class RevocationCheckUnavailableError(AuthDomainError):
    """The revocation list could not be asked; the answer is unknown."""


class RevocationStore(Protocol):
    """List of revoked tokens."""

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Revoke a token.

        Args:
            jti: str - Token id.
            ttl_seconds: int - How long to remember it: until the token expires.

        """
        ...

    async def revoke_if_new(self, jti: str, ttl_seconds: int) -> bool:
        """Revoke a token unless it is revoked already, and say which happened.

        Args:
            jti: str - Token id.
            ttl_seconds: int - How long to remember it: until the token expires.

        Returns:
            bool - True if this call revoked it, False if someone did before.

        Raises:
            RevocationCheckUnavailableError: If the store is down.

        """
        ...

    async def mark_rotated(self, jti: str) -> None:
        """Mark that a successful refresh used `jti` up.

        Args:
            jti: str - Id of the exchanged token.

        """
        ...

    async def was_rotated(self, jti: str) -> bool:
        """Say whether a successful refresh used `jti` up.

        Args:
            jti: str - Id of the presented token.

        Returns:
            bool - True only if the rotation mark is set.

        Raises:
            RevocationCheckUnavailableError: If the store is down.

        """
        ...

    async def is_revoked(self, jti: str) -> bool:
        """Say whether a token is revoked.

        Args:
            jti: str - Token id.

        Returns:
            bool - True if revoked.

        Raises:
            RevocationCheckUnavailableError: If the store is down.

        """
        ...
