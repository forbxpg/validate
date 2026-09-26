"""A journal: its ISSNs, publisher and what Crossref counts about it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated, Self, cast

from pydantic import BeforeValidator, Field, model_validator

from vld.crossref.models import (
    CrossrefModel,
    IssnList,
    OptInt,
    OptIssn,
    OptStr,
    lenient,
)

_MS = 1000
_PAIR = 2


class JournalCounts(CrossrefModel):
    """DOIs of a journal.

    Attributes:
        current_dois: int | None - DOIs of the last two years.
        backfile_dois: int | None - Older DOIs.
        total_dois: int | None - All DOIs.

    """

    current_dois: OptInt = Field(default=None, alias="current-dois")
    backfile_dois: OptInt = Field(default=None, alias="backfile-dois")
    total_dois: OptInt = Field(default=None, alias="total-dois")


class JournalIssn(CrossrefModel):
    """An ISSN of a journal with its kind.

    Attributes:
        type: str | None - ``print`` or ``electronic`` as sent.
        value: str | None - The ISSN, normalized; an invalid one reads as None.

    """

    type: OptStr = None
    value: OptIssn = None


def _one_or_list(value: object) -> object:
    return [value] if isinstance(value, Mapping) else value


def _subject_names(value: object) -> object:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return value
    names: list[object] = []
    for item in value:
        if isinstance(item, Mapping):
            names.append(cast("Mapping[str, object]", item).get("name"))
        else:
            names.append(item)
    return tuple(name for name in names if isinstance(name, str) and name.strip())


def _by_year(value: object) -> object:
    if not isinstance(value, Mapping):
        return value
    pairs = cast("Mapping[str, object]", value).get("dois-by-issued-year")
    if not isinstance(pairs, Sequence) or isinstance(pairs, str):
        return pairs
    return {
        pair[0]: pair[1]
        for pair in pairs
        if isinstance(pair, Sequence) and len(pair) == _PAIR
    }


def _without_check_time(value: object) -> object:
    if not isinstance(value, Mapping):
        return value
    return {
        kind: {
            name: share
            for name, share in cast("Mapping[str, object]", body).items()
            if name != "last-status-check-time"
        }
        for kind, body in cast("Mapping[str, object]", value).items()
        if isinstance(body, Mapping)
    }


def _from_ms(value: object) -> object:
    if isinstance(value, int) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / _MS, UTC)
    return value


class Journal(CrossrefModel):
    """A journal of Crossref. A journal without a valid ISSN is not read.

    Attributes:
        title: str | None - Title.
        publisher: str | None - Publisher.
        issn: tuple[str, ...] - ISSNs, normalized; invalid ones dropped.
        issn_type: tuple[JournalIssn, ...] - ISSNs with kinds.
        subjects: tuple[str, ...] - Subjects, by name.
        counts: JournalCounts | None - DOI counts.
        dois_by_year: Mapping[int, int] - DOIs by issue year.
        coverage: Mapping[str, float] - Share of DOIs with each kind of metadata.
        coverage_type: Mapping[str, Mapping[str, float]] - The same for ``all``,
            ``current`` and ``backfile``.
        flags: Mapping[str, bool] - What the journal deposits.
        last_status_check: datetime | None - When Crossref last counted.

    """

    title: OptStr = None
    publisher: OptStr = None
    issn: IssnList = Field(default=(), alias="ISSN")
    issn_type: Annotated[
        tuple[JournalIssn, ...],
        BeforeValidator(_one_or_list),
        lenient(()),
    ] = Field(default=(), alias="issn-type")
    subjects: Annotated[
        tuple[str, ...],
        BeforeValidator(_subject_names),
        lenient(()),
    ] = ()
    counts: Annotated[JournalCounts | None, lenient(None)] = None
    dois_by_year: Annotated[
        Mapping[int, int],
        BeforeValidator(_by_year),
        lenient({}),
    ] = Field(
        default_factory=dict,
        alias="breakdowns",
    )
    coverage: Annotated[Mapping[str, float], lenient({})] = Field(default_factory=dict)
    coverage_type: Annotated[
        Mapping[str, Mapping[str, float]],
        BeforeValidator(_without_check_time),
        lenient({}),
    ] = Field(default_factory=dict, alias="coverage-type")
    flags: Annotated[Mapping[str, bool], lenient({})] = Field(default_factory=dict)
    last_status_check: Annotated[
        datetime | None,
        BeforeValidator(_from_ms),
        lenient(None),
    ] = Field(
        default=None,
        alias="last-status-check-time",
    )

    @model_validator(mode="after")
    def _has_an_issn(self) -> Self:
        """Refuse a journal no ISSN identifies.

        Returns:
            Self - The journal.

        Raises:
            ValueError: If neither ``ISSN`` nor ``issn-type`` holds a valid ISSN.

        """
        if not self.issns:
            msg = "a journal without a valid ISSN"
            raise ValueError(msg)
        return self

    @property
    def issn_print(self) -> str | None:
        """The print ISSN.

        Returns:
            str | None - The ISSN, or None.

        """
        return self._of_kind("print")

    @property
    def issn_electronic(self) -> str | None:
        """The electronic ISSN.

        Returns:
            str | None - The ISSN, or None.

        """
        return self._of_kind("electronic")

    @property
    def issns(self) -> tuple[str, ...]:
        """Every valid ISSN of the journal, print first, without repeats.

        Returns:
            tuple[str, ...] - The ISSNs.

        """
        typed = [
            entry.value
            for entry in sorted(self.issn_type, key=lambda entry: entry.type != "print")
            if entry.value is not None
        ]
        return tuple(dict.fromkeys([*typed, *self.issn]))

    @property
    def total_dois(self) -> int | None:
        """All DOIs of the journal.

        Returns:
            int | None - The count, or None.

        """
        return None if self.counts is None else self.counts.total_dois

    def _of_kind(self, kind: str) -> str | None:
        return next(
            (
                entry.value
                for entry in self.issn_type
                if entry.type == kind and entry.value
            ),
            None,
        )
