"""Port of the pairs just issued: the grace window of a refresh."""

from __future__ import annotations

from typing import Protocol


class RefreshedPairCache(Protocol):
    """Pairs issued in exchange for a given jti."""

    async def save(
        self,
        jti: str,
        access: str,
        refresh: str,
        ttl_seconds: int,
    ) -> bool:
        """Remember the pair issued for `jti`.

        Args:
            jti: str - Id of the token that was exchanged.
            access: str - Issued access token.
            refresh: str - Issued refresh token.
            ttl_seconds: int - Length of the grace window.

        Returns:
            bool - True if the pair was stored.

        """
        ...

    async def load(self, jti: str) -> tuple[str, str] | None:
        """Return the pair issued for `jti` while the window is open.

        Args:
            jti: str - Id of the presented token.

        Returns:
            tuple[str, str] | None - Access and refresh, or None without a window.

        Raises:
            RevocationCheckUnavailableError: If the store is down.

        """
        ...
