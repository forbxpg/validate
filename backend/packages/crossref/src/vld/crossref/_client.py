"""The client: identity, limits and one HTTP connection pool for every resource."""

from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING, Self, final

from httpx import AsyncClient

from .transport import DEFAULT_RETRY, Identity, Transport

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import TracebackType

    from pydantic import SecretStr

    from .throttle import Throttle
    from .transport import RetryPolicy


@final
class CrossrefClient:
    """Asynchronous client of the Crossref REST API.

    Use it as `async with`. With `http=None` it opens and closes its own
    `AsyncClient`; a passed client is never closed by the library.
    """

    _transport: Transport
    _given_http: AsyncClient | None
    _own_http: AsyncClient | None

    def __init__(  # ruff: ignore[too-many-arguments] -- every setting named at the call site
        self,
        *,
        mailto: str | None,
        throttle: Throttle,
        app: str,
        plus_token: SecretStr | None = None,
        timeout: float = 10.0,
        retry: RetryPolicy = DEFAULT_RETRY,
        http: AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: Callable[[], float] = random.random,  # ruff: ignore[suspicious-non-cryptographic-random-usage]
    ) -> None:
        self._transport = Transport(
            identity=Identity(mailto=mailto, plus_token=plus_token, app=app),
            throttle=throttle,
            retry=retry,
            timeout=timeout,
            clock=clock,
            sleep=sleep,
            rng=rng,
        )
        self._given_http = http
        self._own_http = None

    @property
    def pool(self) -> str | None:
        """The pool Crossref put the last request in.

        Returns:
            str | None - ``x-api-pool`` of the last answer, or None before one.

        """
        return self._transport.pool

    async def __aenter__(self) -> Self:
        """Open the HTTP connection pool.

        Returns:
            Self - The client.

        """
        http = self._given_http
        if http is None:
            http = self._own_http = AsyncClient()
        self._transport.open(http)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the own HTTP connection pool; leave a passed one open.

        Args:
            exc_type: type[BaseException] | None - Type of the error, if any.
            exc: BaseException | None - The error, if any.
            tb: TracebackType | None - Its traceback, if any.

        """
        del exc_type, exc, tb
        self._transport.close()
        if self._own_http is not None:
            await self._own_http.aclose()
            self._own_http = None
