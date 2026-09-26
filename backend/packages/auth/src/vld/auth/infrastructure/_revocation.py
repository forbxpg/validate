"""The revocation list in Redis."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from redis.exceptions import RedisError

from vld.auth.application.ports import RevocationCheckUnavailableError

if TYPE_CHECKING:
    from redis.asyncio import Redis

_PREFIX = "auth:revoked:"

# REVOKED: the token no longer works. ROTATED: it was exchanged for an issued pair.
# Only ROTATED tells a thief from a user who logged out.
_REVOKED = "revoked"
_ROTATED = "rotated"

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


class RedisRevocationStore:
    """Revocation of tokens by jti."""

    def __init__(self, redis: Redis) -> None:
        self._redis: Redis = redis

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Revoke a token.

        Args:
            jti: str - Token id.
            ttl_seconds: int - How long to remember it: until the token expires.

        """
        _ = await self._redis.set(
            f"{_PREFIX}{jti}",
            _REVOKED,
            ex=max(1, ttl_seconds),
            nx=True,
        )

    async def revoke_if_new(self, jti: str, ttl_seconds: int) -> bool:
        """Revoke a token unless it is revoked already.

        Args:
            jti: str - Token id.
            ttl_seconds: int - How long to remember it: until the token expires.

        Returns:
            bool - True if this call revoked it.

        Raises:
            RevocationCheckUnavailableError: If Redis is down.

        """
        try:
            stored = await self._redis.set(
                f"{_PREFIX}{jti}",
                _REVOKED,
                ex=max(1, ttl_seconds),
                nx=True,
            )
        except RedisError as exc:
            _log.exception("revocation_claim_failed", jti=jti)
            msg = "revocation store is unavailable"
            raise RevocationCheckUnavailableError(msg) from exc
        return bool(stored)

    async def mark_rotated(self, jti: str) -> None:
        """Switch the revocation key to "used up by a rotation".

        Args:
            jti: str - Id of the exchanged token.

        """
        try:
            _ = await self._redis.set(
                f"{_PREFIX}{jti}",
                _ROTATED,
                xx=True,
                keepttl=True,
            )
        except RedisError:
            _log.exception("revocation_rotation_mark_failed", jti=jti)

    async def was_rotated(self, jti: str) -> bool:
        """Say whether the revocation key carries the rotation mark.

        Args:
            jti: str - Id of the presented token.

        Returns:
            bool - True if a successful rotation used the jti up.

        Raises:
            RevocationCheckUnavailableError: If Redis is down.

        """
        try:
            return await self._redis.get(f"{_PREFIX}{jti}") == _ROTATED
        except RedisError as exc:
            _log.exception("revocation_rotation_check_failed", jti=jti)
            msg = "revocation store is unavailable"
            raise RevocationCheckUnavailableError(msg) from exc

    async def is_revoked(self, jti: str) -> bool:
        """Say whether a token is revoked.

        Args:
            jti: str - Token id.

        Returns:
            bool - True if revoked.

        Raises:
            RevocationCheckUnavailableError: If Redis is down.

        """
        try:
            return await self._redis.exists(f"{_PREFIX}{jti}") == 1
        except RedisError as exc:
            _log.exception("revocation_check_failed", jti=jti)
            msg = "revocation store is unavailable"
            raise RevocationCheckUnavailableError(msg) from exc
