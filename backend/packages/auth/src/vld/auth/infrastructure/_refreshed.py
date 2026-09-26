"""Pairs just issued, in Redis: the grace window of a refresh."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import structlog
from redis.exceptions import RedisError

from vld.auth.application.ports import RevocationCheckUnavailableError

if TYPE_CHECKING:
    from redis.asyncio import Redis

_PREFIX = "auth:refreshed:"

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


class RedisRefreshedPairCache:
    """Pair issued for a jti, under the key `auth:refreshed:{jti}`."""

    def __init__(self, redis: Redis) -> None:
        self._redis: Redis = redis

    async def save(
        self,
        jti: str,
        access: str,
        refresh: str,
        ttl_seconds: int,
    ) -> bool:
        """Store the pair under the old jti for the grace window.

        Args:
            jti: str - Id of the presented token.
            access: str - Issued access token.
            refresh: str - Issued refresh token.
            ttl_seconds: int - Length of the grace window.

        Returns:
            bool - True if the pair was stored.

        """
        payload = json.dumps({"access": access, "refresh": refresh})
        try:
            _ = await self._redis.set(f"{_PREFIX}{jti}", payload, ex=ttl_seconds)
        except RedisError:
            _log.exception("refreshed_pair_save_failed", jti=jti)
            return False
        return True

    async def load(self, jti: str) -> tuple[str, str] | None:
        """Read the pair while the grace window is open.

        Args:
            jti: str - Id of the presented token.

        Returns:
            tuple[str, str] | None - Access and refresh, or None.

        Raises:
            RevocationCheckUnavailableError: If Redis is down.

        """
        try:
            raw = await self._redis.get(f"{_PREFIX}{jti}")
        except RedisError as exc:
            _log.exception("refreshed_pair_load_failed", jti=jti)
            msg = "refreshed pair cache is unavailable"
            raise RevocationCheckUnavailableError(msg) from exc
        if raw is None:
            return None
        try:
            data = cast("object", json.loads(raw))
        except json.JSONDecodeError:
            _log.warning("refreshed_pair_malformed", jti=jti)
            return None
        match data:
            case {"access": str(access), "refresh": str(refresh)}:
                return access, refresh
            case _:
                _log.warning("refreshed_pair_malformed", jti=jti)
                return None
