"""Port of the current time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    """Source of the current time."""

    @classmethod
    def now(cls) -> datetime:
        """Tell the current moment.

        Returns:
            datetime - Time in UTC.

        """
        ...
