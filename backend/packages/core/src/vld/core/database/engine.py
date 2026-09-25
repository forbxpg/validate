"""Async engine и фабрика сессий."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from vld.core.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create engine for the application (through PgBouncer).

    Args:
        settings: DatabaseSettings - Connection settings.

    Returns:
        AsyncEngine - Engine for the application.

    """
    connect_args: dict[str, object] = {}

    if settings.disable_prepared_statements:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    return create_async_engine(
        str(settings.dsn),
        echo=settings.echo,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=settings.pool_pre_ping,
        connect_args=connect_args,
    )


def create_migration_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create engine for migrations — directly to PostgreSQL, bypassing the pool.

    Args:
        settings: DatabaseSettings - Connection settings.

    Returns:
        AsyncEngine - Engine for Alembic.

    """
    return create_async_engine(
        settings.migration_dsn,
        echo=settings.echo,
        poolclass=NullPool,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create session factory.

    Args:
        engine: AsyncEngine - Engine, to which the sessions are attached.

    Returns:
        async_sessionmaker[AsyncSession] - Session factory.

    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def dispose_engine(engine: AsyncEngine) -> None:
    """Close all connections to the engine.

    Args:
        engine: AsyncEngine - Engine, which we are closing.

    """
    await engine.dispose()
