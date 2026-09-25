"""Async engine and session factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from vld.core.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create the application engine.

    Args:
        settings: DatabaseSettings - Connection and pool settings.

    Returns:
        AsyncEngine - Engine with a connection pool.

    """
    return create_async_engine(
        str(settings.url),
        echo=settings.echo,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout,
        pool_pre_ping=settings.pool_pre_ping,
        pool_recycle=settings.pool_recycle,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory.

    Args:
        engine: AsyncEngine - Engine the sessions are bound to.

    Returns:
        async_sessionmaker[AsyncSession] - Session factory.

    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
