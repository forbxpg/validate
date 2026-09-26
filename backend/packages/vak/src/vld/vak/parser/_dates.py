"""The date cell of a speciality group: «с ДД.ММ.ГГГГ» and maybe «по ДД.ММ.ГГГГ»."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from vld.vak.models import WarningCode

from ._finding import Finding

_CANONICAL = re.compile(r"с (\d{2}\.\d{2}\.\d{4})(?: по (\d{2}\.\d{2}\.\d{4}))?")
# Latin «c» and a capital, spaced digits, «п о» and «до» for «по», a trailing dot.
_LOOSE = re.compile(
    r"(?:[сСcC]\s*)?(?P<start>[\d\s.]+?)\s*(?:(?:п\s*о|до)\s*(?P<end>[\d\s.]+?))?\s*\.?",
)
_DATE_DIGITS = 8


@dataclass(frozen=True, slots=True)
class DateCell:
    """What a date cell gave.

    Attributes:
        included: date | None - The «с» date.
        excluded: date | None - The «по» date.
        finding: Finding | None - A repair or a failure to read.

    """

    included: date | None
    excluded: date | None
    finding: Finding | None


def read_dates(printed: str) -> DateCell:
    """Read the dates of a group; repair what is unambiguous and say so.

    Args:
        printed: str - The cell, whitespace collapsed, not empty.

    Returns:
        DateCell - The dates, and a finding when the cell was not canonical.

    """
    canonical = _CANONICAL.fullmatch(printed)
    if canonical is not None:
        included, excluded = (
            parse_day(canonical.group(1)),
            _optional_day(canonical.group(2)),
        )
        if included is not None and (
            canonical.group(2) is None or excluded is not None
        ):
            return DateCell(included, excluded, None)
    loose = _LOOSE.fullmatch(printed)
    if loose is not None:
        included = _digits_day(loose.group("start"))
        end = loose.group("end")
        excluded = None if end is None else _digits_day(end)
        if included is not None and (end is None or excluded is not None):
            shown = f"с {included:%d.%m.%Y}" + (
                "" if excluded is None else f" по {excluded:%d.%m.%Y}"
            )
            return DateCell(
                included,
                excluded,
                Finding(WarningCode.DATE_REPAIRED, printed, f"read as {shown!r}"),
            )
    return DateCell(
        None,
        None,
        Finding(WarningCode.DATE_UNRECOGNIZED, printed, "no «с ДД.ММ.ГГГГ» date"),
    )


def _optional_day(text: str | None) -> date | None:
    return None if text is None else parse_day(text)


def _digits_day(text: str) -> date | None:
    digits = re.sub(r"\D", "", text)
    if len(digits) != _DATE_DIGITS:
        return None
    return parse_day(f"{digits[:2]}.{digits[2:4]}.{digits[4:]}")


def parse_day(text: str) -> date | None:
    """Read a canonical ``ДД.ММ.ГГГГ`` date.

    Args:
        text: str - The date.

    Returns:
        date | None - The date, or None if it is not a real one.

    """
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()  # ruff: ignore[call-datetime-strptime-without-zone] - a calendar date, no time
    except ValueError:
        return None
