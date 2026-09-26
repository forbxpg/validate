"""Password hashing with bcrypt, the scheme of doi-arxiv-app."""

from __future__ import annotations

import bcrypt
from anyio import CapacityLimiter, to_thread

# Cost of doi-arxiv-app (the bcrypt default): its hashes keep working after ETL.
BCRYPT_ROUNDS = 12

# bcrypt reads only 72 bytes and refuses longer input.
_MAX_PASSWORD_BYTES = 72

# A cost-12 hash takes a CPU core for about a quarter of a second.
_MAX_CONCURRENT_HASHES = 4

# Per process, not per instance: it guards the CPU of the machine.
_LIMITER = CapacityLimiter(_MAX_CONCURRENT_HASHES)


def _cost(password_hash: str) -> int | None:
    """Read the cost out of a bcrypt hash such as `$2b$12$...`.

    Args:
        password_hash: str - Stored hash.

    Returns:
        int | None - The cost, or None if the hash is not bcrypt.

    """
    parts = password_hash.split("$")
    if len(parts) < 4 or not parts[2].isdigit():  # ruff: ignore[magic-value-comparison] -- "", "2b", cost, rest
        return None
    return int(parts[2])


class BcryptPasswordHasher:
    """bcrypt in a thread, with a ceiling on concurrent hashes."""

    def __init__(
        self,
        rounds: int = BCRYPT_ROUNDS,
        limiter: CapacityLimiter = _LIMITER,
    ) -> None:
        self._rounds: int = rounds
        self._limiter: CapacityLimiter = limiter

    async def hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: str - Plain password, at most 72 bytes.

        Returns:
            str - Hash with its cost and salt.

        """
        salt = bcrypt.gensalt(rounds=self._rounds)
        digest = await to_thread.run_sync(
            bcrypt.hashpw,
            password.encode(),
            salt,
            limiter=self._limiter,
        )
        return digest.decode()

    async def verify(self, password: str, password_hash: str) -> bool:
        """Check a password against a hash.

        Args:
            password: str - Plain password.
            password_hash: str - Stored hash.

        Returns:
            bool - True if they match; a password over 72 bytes never does.

        """
        encoded = password.encode()
        if len(encoded) > _MAX_PASSWORD_BYTES:
            return False
        return await to_thread.run_sync(
            bcrypt.checkpw,
            encoded,
            password_hash.encode(),
            limiter=self._limiter,
        )

    def needs_rehash(self, password_hash: str) -> bool:
        """Say whether a hash was made with a lower cost than the current one.

        Args:
            password_hash: str - Stored hash.

        Returns:
            bool - True if it should be hashed again.

        """
        cost = _cost(password_hash)
        return cost is None or cost < self._rounds
