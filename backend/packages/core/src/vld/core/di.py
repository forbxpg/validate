"""Инфраструктурные DI-провайдеры, общие для всех деплой-приложений."""

from __future__ import annotations

from collections.abc import (
    AsyncIterator,  # ruff: ignore[typing-only-standard-library-import]
)

from dishka import (
    Provider,
    Scope,
    ValidationSettings,
    provide,  # pyright: ignore[reportUnknownVariableType]
)
from sqlalchemy.ext.asyncio import (  # ruff: ignore[typing-only-third-party-import]
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from vld.core.audit import (
    AuditLog,
    AuditQuery,
    SqlAlchemyAuditLog,
    SqlAlchemyAuditQuery,
)
from vld.core.config import (
    DatabaseSettings,
    RedisSettings,
    SecuritySettings,
    get_database_settings,
    get_redis_settings,
    get_security_settings,
)
from vld.core.database import (
    SqlAlchemyUnitOfWork,
    UnitOfWork,
    create_engine,
    create_session_factory,
    dispose_engine,
)

CONTAINER_VALIDATION = ValidationSettings(implicit_override=True)


class CoreProvider(Provider):
    """Инфраструктурные зависимости, общие для всех доменов."""

    @provide(scope=Scope.APP)
    def database_settings(self) -> DatabaseSettings:  # ruff: ignore[no-self-use]
        """Database settings.

        Returns:
            DatabaseSettings - Settings.

        """
        return get_database_settings()

    @provide(scope=Scope.APP)
    def redis_settings(self) -> RedisSettings:  # ruff: ignore[no-self-use]
        """Redis settings.

        Returns:
            RedisSettings - Settings.

        """
        return get_redis_settings()

    @provide(scope=Scope.APP)
    def security_settings(self) -> SecuritySettings:  # ruff: ignore[no-self-use]
        """Security settings.

        Returns:
            SecuritySettings - Settings.

        """
        return get_security_settings()

    @provide(scope=Scope.APP)
    async def engine(self, settings: DatabaseSettings) -> AsyncIterator[AsyncEngine]:  # ruff: ignore[no-self-use]
        """Application engine.

        Args:
            settings: DatabaseSettings - Database settings.

        Yields:
            AsyncEngine - Engine, closed on shutdown.

        """
        engine = create_engine(settings)
        yield engine
        await dispose_engine(engine)

    @provide(scope=Scope.APP)
    def session_factory(  # ruff: ignore[no-self-use]
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        """Session factory.

        Args:
            engine: AsyncEngine - Engine.

        Returns:
            async_sessionmaker[AsyncSession] - Factory.

        """
        return create_session_factory(engine)

    @provide(scope=Scope.REQUEST)
    def audit(self, session: AsyncSession) -> AuditLog:  # ruff: ignore[no-self-use]
        """Audit log.

        Args:
            session: AsyncSession - SQLAlchemy session.

        Returns:
            AuditLog - Implementation over the session.

        """
        return SqlAlchemyAuditLog(session)

    @provide(scope=Scope.REQUEST)
    def audit_query(self, session: AsyncSession) -> AuditQuery:  # ruff: ignore[no-self-use]
        """Audit query.

        Args:
            session: AsyncSession - SQLAlchemy session.

        Returns:
            AuditQuery - Implementation over the session.

        """
        return SqlAlchemyAuditQuery(session)

    @provide(scope=Scope.REQUEST)
    def uow(self, session: AsyncSession) -> UnitOfWork:  # ruff: ignore[no-self-use]
        """Request transaction boundary.

        Args:
            session: AsyncSession - SQLAlchemy session.

        Returns:
            UnitOfWork - Implementation over the session.

        """
        return SqlAlchemyUnitOfWork(session)

    @provide(scope=Scope.REQUEST)
    async def session(  # ruff: ignore[no-self-use]
        self,
        factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        """Request session.

        Args:
            factory: async_sessionmaker[AsyncSession] - Session factory.

        Yields:
            AsyncSession - Session, closed on request completion.

        """
        async with factory() as session:
            yield session  # ruff: ignore[yield-in-context-manager-in-async-generator]
