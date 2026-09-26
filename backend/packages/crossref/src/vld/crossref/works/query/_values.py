"""Types of filter values: how they are accepted, checked and written for Crossref."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from enum import Enum
from typing import Annotated, cast

from pydantic import AfterValidator, BeforeValidator

from vld.crossref.errors import CrossrefQueryError
from vld.crossref.ids import (
    normalize_doi,
    normalize_issn,
    normalize_orcid,
    normalize_prefix,
    normalize_ror,
)
from vld.crossref.models import PartialDate

from ._enums import FullTextApplication, LicenseVersion, WorkType


def _as_tuple(value: object) -> object:
    if value is None or isinstance(value, tuple):
        return value
    if isinstance(value, (str, int, Enum)):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return value


def _each(normalize: Callable[[str], str]) -> AfterValidator:
    def _apply(values: object) -> object:
        if not isinstance(values, tuple):
            return values
        return tuple(
            normalize(str(value)) for value in cast("tuple[object, ...]", values)
        )

    return AfterValidator(_apply)


def _no_comma(value: str) -> str:
    if "," in value:
        msg = f"Crossref cannot filter by a value with a comma: {value!r}"
        raise CrossrefQueryError(msg)
    return value


def _aware_utc(value: object) -> object:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            msg = f"a datetime filter must be aware: {value!r}"
            raise CrossrefQueryError(msg)
        return value.astimezone(UTC)
    return value


type _Many[T] = T | Sequence[T] | None

ManyStr = Annotated[_Many[str], BeforeValidator(_as_tuple), _each(_no_comma)]
"""One string or several; each without a comma."""

ManyDoi = Annotated[_Many[str], BeforeValidator(_as_tuple), _each(normalize_doi)]
ManyIssn = Annotated[_Many[str], BeforeValidator(_as_tuple), _each(normalize_issn)]
ManyOrcid = Annotated[_Many[str], BeforeValidator(_as_tuple), _each(normalize_orcid)]
ManyRor = Annotated[_Many[str], BeforeValidator(_as_tuple), _each(normalize_ror)]
ManyPrefix = Annotated[_Many[str], BeforeValidator(_as_tuple), _each(normalize_prefix)]
ManyInt = Annotated[_Many[int], BeforeValidator(_as_tuple)]
ManyWorkType = Annotated[_Many[WorkType], BeforeValidator(_as_tuple)]
ManyLicenseVersion = Annotated[_Many[LicenseVersion], BeforeValidator(_as_tuple)]
ManyFullTextApplication = Annotated[
    _Many[FullTextApplication],
    BeforeValidator(_as_tuple),
]

DateBound = PartialDate | date | None
"""A publication-side date: a PartialDate of any precision or a date."""

DepositBound = Annotated[
    datetime | PartialDate | date | None,
    BeforeValidator(_aware_utc),
]
"""A deposit-side moment: also an aware datetime, sent in UTC."""


def render_value(value: object) -> str:
    """Write one filter value as Crossref reads it.

    Args:
        value: object - A bool, number, enum, date, datetime, PartialDate or string.

    Returns:
        str - The value in Crossref's form.

    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        return str(cast("object", value.value))
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def earliest(value: object) -> date | None:
    """First day a date bound can mean.

    Args:
        value: object - A date bound or None.

    Returns:
        date | None - The first day, or None for None.

    """
    if isinstance(value, PartialDate):
        return value.earliest()
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def latest(value: object) -> date | None:
    """Last day a date bound can mean.

    Args:
        value: object - A date bound or None.

    Returns:
        date | None - The last day, or None for None.

    """
    if isinstance(value, PartialDate):
        return value.latest()
    return earliest(value)
