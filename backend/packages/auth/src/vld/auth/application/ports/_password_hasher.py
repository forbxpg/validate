"""Port of password hashing."""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    """Hashing and checking passwords."""

    async def hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: str - Plain password.

        Returns:
            str - The hash.

        """
        ...

    async def verify(self, password: str, password_hash: str) -> bool:
        """Check a password against a hash.

        Args:
            password: str - Plain password.
            password_hash: str - Stored hash.

        Returns:
            bool - True if they match.

        """
        ...

    def needs_rehash(self, password_hash: str) -> bool:
        """Say whether a hash was made with outdated parameters.

        Args:
            password_hash: str - Stored hash.

        Returns:
            bool - True if it should be hashed again.

        """
        ...
