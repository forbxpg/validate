"""Dates as precise as Crossref knows them, never more."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from functools import total_ordering
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast, override

from pydantic import BeforeValidator, Field

from ._base import CrossrefModel
from ._lenient import degraded, lenient

if TYPE_CHECKING:
    from pydantic import ValidationInfo


_MAX_YEAR: Final[int] = 9999
"""The last year of the 20th century."""

_MAX_MONTH: Final[int] = 12
"""The last month of the year."""


@total_ordering
@dataclass(frozen=True, slots=True)
class PartialDate:
    """A date known to the year, the month or the day.

    Attributes:
        year: int - Year.
        month: int | None - Month, when known.
        day: int | None - Day, when known; never without a month.

    """

    year: int
    month: int | None = None
    day: int | None = None

    def __post_init__(self) -> None:
        """Refuse a date that cannot exist.

        Raises:
            ValueError: If the year, month or day is out of range, or a day has
                no month.

        """
        if not 1 <= self.year <= _MAX_YEAR:
            msg = f"year {self.year} is out of range"
            raise ValueError(msg)
        if self.month is not None and not 1 <= self.month <= _MAX_MONTH:
            msg = f"month {self.month} is out of range"
            raise ValueError(msg)
        if self.day is not None:
            if self.month is None:
                msg = "day has no month"
                raise ValueError(msg)
            _ = date(self.year, self.month, self.day)

    def earliest(self) -> date:
        """Give the first day the date can mean.

        Returns:
            date - The first possible day.

        """
        return date(self.year, self.month or 1, self.day or 1)

    def latest(self) -> date:
        """Give the last day the date can mean.

        Returns:
            date - The last possible day.

        """
        month = self.month or _MAX_MONTH
        day = self.day or monthrange(self.year, month)[1]
        return date(self.year, month, day)

    def precision(self) -> Literal["year", "month", "day"]:
        """Tell how precise the date is.

        Returns:
            Literal["year", "month", "day"] - The precision.

        """
        if self.day is not None:
            return "day"
        if self.month is not None:
            return "month"
        return "year"

    def _key(self) -> tuple[int, int, int]:
        return (self.year, self.month or 0, self.day or 0)

    def __lt__(self, other: object) -> bool:
        """Order dates, a less precise one before the more precise ones in it.

        Args:
            other: object - Date to compare with.

        Returns:
            bool - True if this date sorts first.

        """
        if not isinstance(other, PartialDate):
            return NotImplemented
        return self._key() < other._key()

    @override
    def __str__(self) -> str:
        """Write the date as precisely as it is known.

        Returns:
            str - "2020", "2020-05" or "2020-05-17".

        """
        if self.month is None:
            return f"{self.year:04d}"
        if self.day is None:
            return f"{self.year:04d}-{self.month:02d}"
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _first_parts(value: object) -> Sequence[object] | None:
    parts = (
        cast("Mapping[str, object]", value).get("date-parts")
        if isinstance(value, Mapping)
        else value
    )
    if not isinstance(parts, Sequence) or isinstance(parts, str) or not parts:
        return None
    first = parts[0]
    if not isinstance(first, Sequence) or isinstance(first, str) or not first:
        return None
    return first


def _closest(
    year: int,
    month: int | None,
    day: int | None,
    field: str | None,
) -> PartialDate:
    try:
        return PartialDate(year, month, day)
    except ValueError:
        degraded(field, f"impossible date {year}-{month}-{day}")
    try:
        return PartialDate(year, month)
    except ValueError:
        return PartialDate(year)


def from_date_parts(value: object, info: ValidationInfo) -> object:
    """Read {"date-parts": [[y, m, d]]} or [[y, m, d]] into a PartialDate.

    An impossible month or day is dropped with a warning; the year stays.

    Args:
        value: object - The raw value.
        info: ValidationInfo - Context of the field, for the warning.

    Returns:
        object - A PartialDate, None, or the value untouched for pydantic to refuse.

    """
    if value is None or isinstance(value, PartialDate):
        return value
    first = _first_parts(value)
    if first is None:
        return value
    year = _int_or_none(first[0])
    if year is None:
        return None
    month = _int_or_none(first[1]) if len(first) > 1 else None
    day = _int_or_none(first[2]) if len(first) > 2 and month is not None else None  # ruff: ignore[magic-value-comparison]
    return _closest(year, month, day, info.field_name)


CrossrefDate = Annotated[
    PartialDate | None,
    BeforeValidator(from_date_parts),
    lenient(None),
]
"""A date-parts field; malformed data reads as None."""


class CrossrefTimestamp(CrossrefModel):
    """A moment Crossref stamps (``created``, ``deposited``, ``indexed``).

    Attributes:
        parts: PartialDate - The date part.
        date_time: datetime - The moment, aware.
        timestamp_ms: int - Unix time in milliseconds.

    """

    parts: Annotated[
        PartialDate,
        BeforeValidator(
            from_date_parts,
        ),
    ] = Field(
        alias="date-parts",
    )
    date_time: datetime = Field(alias="date-time")
    timestamp_ms: int = Field(alias="timestamp")
