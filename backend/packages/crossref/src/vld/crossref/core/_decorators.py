"""Decorators for Crossref async API client."""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from ._errors import CrossrefClientError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import CoroutineType

P = ParamSpec("P")
T = TypeVar("T")


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[Exception]] = (Exception,),
) -> Callable[
    [Callable[P, Awaitable[T]]],
    Callable[P, CoroutineType[object, object, T]],
]:
    """Retry decorator.

    Returns:
        The returned value.

    """

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, CoroutineType[object, object, T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            for _ in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    await asyncio.sleep(delay)

            msg = f"Не удалось выполнить запрос после {max_retries} попыток"
            raise CrossrefClientError(msg) from last_exception

        return wrapper

    return decorator
