"""The part of the Redis client that the limiter uses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Sequence


class RedisScript(Protocol):
    """A Lua script registered on the server."""

    def __call__(
        self,
        keys: Sequence[str] | None = None,
        args: Sequence[int] | None = None,
    ) -> Awaitable[list[int]]:
        """Run the script.

        Args:
            keys: Sequence[str] | None - Redis keys, `KEYS` in the script.
            args: Sequence[int] | None - Script arguments, `ARGV` in the script.

        Returns:
            Awaitable[list[int]] - What the script returns.

        """
        ...


class RedisLike(Protocol):
    """The minimum of `redis.asyncio.Redis` that the limiter needs."""

    def register_script(self, script: str) -> RedisScript:
        """Register a Lua script.

        Args:
            script: str - Source of the Lua script.

        Returns:
            RedisScript - The script, ready to be called.

        """
        ...

    def delete(self, *names: str) -> Awaitable[int]:
        """Delete keys.

        Args:
            names: str - Keys to delete.

        Returns:
            Awaitable[int] - How many keys were deleted.

        """
        ...
