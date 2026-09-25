"""Port of the transaction boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from types import TracebackType


class UnitOfWork(ABC):
    """Port of the transaction boundary."""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Enter the transaction.

        Returns:
            Self - The UnitOfWork itself.

        """

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the transaction, rolling back the uncommitted changes.

        Args:
            exc_type: type[BaseException] | None - Type of the exception, if any.
            exc: BaseException | None - The exception itself, if any.
            tb: TracebackType | None - The traceback, if any.

        """

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""

    @abstractmethod
    async def flush(self) -> None:
        """Send the accumulated changes to the database.

        Without committing the transaction.

        """
