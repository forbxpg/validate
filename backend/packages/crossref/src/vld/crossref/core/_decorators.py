"""Decorators for the Crossref async API client."""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING

from ._errors import (
    CrossrefRateLimitError,
    CrossrefRequestTimeoutError,
    CrossrefServerError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    CrossrefRateLimitError,
    CrossrefRequestTimeoutError,
    CrossrefServerError,
)
"""Errors that another call may not repeat: rate limit, timeout, 5xx."""


def retry[**P, T](
    attempts: int = 3,
    delay_seconds: float = 1.0,
    errors: tuple[type[Exception], ...] = TRANSIENT_ERRORS,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Call an async function again when it fails with a transient error.

    The last error is raised as it is, so its type still tells a timeout from a
    rate limit; any other error is raised at once, without another call.

    Args:
        attempts: int - Calls in total, the first one included.
        delay_seconds: float - Pause between two calls.
        errors: tuple[type[Exception], ...] - Errors worth another call.

    Returns:
        Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]] - The
            decorator.

    Raises:
        ValueError: If `attempts` is below 1.

    """
    if attempts < 1:
        msg = "attempts must be at least 1"
        raise ValueError(msg)

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for _ in range(attempts - 1):
                try:
                    return await func(*args, **kwargs)
                except errors:
                    await asyncio.sleep(delay_seconds)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
