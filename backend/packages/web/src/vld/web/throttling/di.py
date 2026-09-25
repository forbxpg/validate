"""Ограничитель частоты: единственная привязка протокола к реализации."""

from __future__ import annotations

from collections.abc import AsyncIterator

from dishka import (
    Provider,
    Scope,
    provide,  # pyright: ignore[reportUnknownVariableType]
)

from shoptest.core.config import RedisSettings
from shoptest.core.ratelimit import RateLimiter
from shoptest.core.redis import redis_client
from shoptest.web.throttling._throttle import Limiter


class ThrottlingProvider(Provider):
    """Ограничитель частоты, общий для всех доменов-потребителей."""

    @provide(scope=Scope.APP, override=True)
    async def limiter(self, settings: RedisSettings) -> AsyncIterator[Limiter]:
        """Ограничитель частоты поверх Redis.

        Args:
            settings: RedisSettings - Адрес Redis и номер базы под счётчики.

        Yields:
            Limiter - Ограничитель поверх Redis, клиент закрывается на остановке
                приложения.

        """
        async for client in redis_client(str(settings.dsn), settings.counters_db):
            yield RateLimiter(client)
