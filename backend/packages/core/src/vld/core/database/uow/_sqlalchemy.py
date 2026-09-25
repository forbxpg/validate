"""Implementation of `UnitOfWork` over `AsyncSession`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, override

from ._port import UnitOfWork

if TYPE_CHECKING:
    from types import TracebackType

    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Implementation of UnitOfWork over AsyncSession."""

    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Session for repositories.

        Returns:
            AsyncSession - Active session.

        """
        return self._session

    @override
    async def __aenter__(self) -> Self:
        """Enter the transaction.

        Returns:
            Self - The UnitOfWork itself.

        """
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the transaction.

        Args:
            exc_type: type[BaseException] | None - Type of the exception, if any.
            exc: BaseException | None - The exception itself, if any.
            tb: TracebackType | None - The traceback, if any.

        """
        await self._session.rollback()

    @override
    async def commit(self) -> None:
        """Commit the transaction."""
        await self._session.commit()

    @override
    async def rollback(self) -> None:
        """Rollback the transaction."""
        await self._session.rollback()

    @override
    async def flush(self) -> None:
        """Send the accumulated changes to the database.

        Without committing the transaction.

        """
        await self._session.flush()
