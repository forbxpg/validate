"""Port for the Redis client."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Coroutine


class RedisLike(Protocol):
    """The minimum from the Redis client, needed by the limiter."""

    def register_script(self, script: str) -> RedisLikeScriptRunner:
        """Compiles the Lua script on the server side.

        Args:
            script: str - The source code of the Lua script.

        Returns:
            _ScriptRunner - The callable compiled script.

        """
        ...

    def delete(self, *keys: str) -> Coroutine[Any, Any, int]:
        """Deletes the keys.

        Args:
            keys: str - Keys to delete.

        Returns:
            Awaitable[int] - How many keys were deleted.

        """
        ...


class RedisLikeScriptRunner(Protocol):
    """Compiled Redis Lua script."""

    def __call__(self, keys: list[str], args: list[int]) -> Awaitable[Any]:  # pyright: ignore[reportReturnType, reportExplicitAny]
        """Calls the script with keys and arguments.

        Args:
            keys: list[str] - Redis keys (`KEYS` in the script).
            args: list[int] - Arguments of the script (`ARGV`).

        Returns:
            Awaitable[list[int]] - The result of the script: [count, ttl_ms].

        """
