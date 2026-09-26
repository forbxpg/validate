"""The system clock."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """System time in UTC."""

    @classmethod
    def now(cls) -> datetime:
        """Tell the current moment.

        Returns:
            datetime - Time in UTC.

        """
        return datetime.now(UTC)
