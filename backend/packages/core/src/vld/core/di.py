"""Infrastructure providers shared by every deployable app."""

from __future__ import annotations

from collections.abc import AsyncIterator

from dishka import Provider, Scope, ValidationSettings, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from vld.core.config import DatabaseSettings, RedisSettings
from vld.core.database import (
    SqlAlchemyUnitOfWork,
    UnitOfWork,
    create_engine,
    create_session_factory,
)

CONTAINER_VALIDATION = ValidationSettings(implicit_override=True)


class CoreProvider(Provider):
    """Settings, database and Redis for every domain."""

    # Settings have required fields that pydantic reads from the environment;
    # basedpyright only sees a constructor call with missing arguments.

    @provide(scope=Scope.APP)
    def database_settings(self) -> DatabaseSettings:
        """Read the database settings.

        Returns:
            DatabaseSettings - Settings from `DATABASE_*`.

        """
        return DatabaseSettings()  # pyright: ignore[reportCallIssue]

    @provide(scope=Scope.APP)
    def redis_settings(self) -> RedisSettings:
        """Read the Redis settings.

        Returns:
            RedisSettings - Settings from `REDIS_*`.

        """
        return RedisSettings()  # pyright: ignore[reportCallIssue]

    @provide(scope=Scope.APP)
    async def engine(self, settings: DatabaseSettings) -> AsyncIterator[AsyncEngine]:
        """Open the application engine.

        Args:
            settings: DatabaseSettings - Database settings.

        Yields:
            AsyncEngine - Engine, disposed on shutdown.

        """
        engine = create_engine(settings)
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    def session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        """Build the session factory.

        Args:
            engine: AsyncEngine - Engine.

        Returns:
            async_sessionmaker[AsyncSession] - Session factory.

        """
        return create_session_factory(engine)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        """Open the request session.

        Args:
            factory: async_sessionmaker[AsyncSession] - Session factory.

        Yields:
            AsyncSession - Session, closed when the request ends.

        """
        async with factory() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    def uow(self, session: AsyncSession) -> UnitOfWork:
        """Bind the transaction boundary to the request session.

        Args:
            session: AsyncSession - Request session.

        Returns:
            UnitOfWork - Unit of work over the session.

        """
        return SqlAlchemyUnitOfWork(session)

    @provide(scope=Scope.APP)
    async def redis(self, settings: RedisSettings) -> AsyncIterator[Redis]:
        """Open the Redis client.

        Args:
            settings: RedisSettings - Redis settings.

        Yields:
            Redis - Client, closed on shutdown.

        """
        password = settings.password.get_secret_value() if settings.password else None
        client = Redis(
            host=settings.host,
            port=settings.port,
            db=settings.db,
            username=settings.username,
            password=password,
            decode_responses=True,
        )
        yield client
        await client.aclose()
