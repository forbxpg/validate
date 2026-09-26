"""Audit log port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._entry import AuditEntry


class AuditLog(ABC):
    """Port for recording audit log."""

    @abstractmethod
    async def record(self, entry: AuditEntry) -> None:
        """Record an event in the current transaction.

        Args:
            entry: AuditEntry - Event.

        Raises:
            Exception - any storage rejection.

        """
