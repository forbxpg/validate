"""Rows into journals: a state machine over the rows of every page, in order."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vld.vak.models import ParseWarning, SpecialityGroup, VakJournal, WarningCode

from ._dates import read_dates
from ._finding import Finding, flatten
from ._issn import read_issns
from ._specialities import read_specialities
from ._title import read_title

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ._extract import Row

_NUMBER = re.compile(r"(\d+)\.?")


@dataclass(frozen=True, slots=True)
class Assembled:
    """The journals of the rows and every warning found on the way.

    Attributes:
        journals: tuple[VakJournal, ...] - In print order.
        warnings: tuple[ParseWarning, ...] - Row, cell and numbering warnings.

    """

    journals: tuple[VakJournal, ...]
    warnings: tuple[ParseWarning, ...]


@dataclass(slots=True)
class _Group:
    page: int
    dates: str
    texts: list[str]


@dataclass(slots=True)
class _Journal:
    number: int
    pages: list[int]
    titles: list[str] = field(default_factory=list)
    issns: list[str] = field(default_factory=list)
    groups: list[_Group] = field(default_factory=list)


def assemble(rows: Sequence[Row]) -> Assembled:
    """Build the journals from the rows.

    A row with a number starts a journal; a row without one continues it. A date
    cell starts a speciality group; a row with specialities and no date continues
    the group above, so a speciality cut by a row or a page break is joined again.

    Args:
        rows: Sequence[Row] - Rows of every page, in order, header rows left out.

    Returns:
        Assembled - Journals and warnings.

    """
    drafts: list[_Journal] = []
    warnings: list[ParseWarning] = []
    for row in rows:
        cells = (row.number, row.title, row.issn, row.specialities, row.dates)
        if not any(cell.strip() for cell in cells):
            continue
        number = _NUMBER.fullmatch(row.number.strip())
        if number is not None:
            drafts.append(_Journal(number=int(number.group(1)), pages=[row.page]))
        elif row.number.strip() or not drafts:
            warnings.append(_unrecognized(row))
            continue
        _add(drafts[-1], row)
    journals = [_journal(draft, warnings) for draft in drafts]
    warnings.extend(_numbering([journal.number for journal in journals]))
    return Assembled(tuple(journals), tuple(warnings))


def _add(draft: _Journal, row: Row) -> None:
    if row.page not in draft.pages:
        draft.pages.append(row.page)
    if row.title.strip():
        draft.titles.append(row.title)
    if row.issn.strip():
        draft.issns.append(row.issn)
    if row.dates.strip() or not draft.groups:
        draft.groups.append(
            _Group(page=row.page, dates=row.dates, texts=[row.specialities]),
        )
    elif row.specialities.strip():
        draft.groups[-1].texts.append(row.specialities)


def _journal(draft: _Journal, warnings: list[ParseWarning]) -> VakJournal:
    first = draft.pages[0]
    title = read_title(flatten("\n".join(draft.titles)))
    issns = read_issns("\n".join(draft.issns))
    warnings.extend(_warnings(title.findings, first, draft.number))
    warnings.extend(_warnings(issns.findings, first, draft.number))
    groups = tuple(_group(group, draft.number, warnings) for group in draft.groups)
    groups = tuple(
        group for group in groups if group.specialities or group.dates_printed
    )
    if not any(group.specialities for group in groups):
        warnings.append(
            ParseWarning(
                code=WarningCode.JOURNAL_WITHOUT_SPECIALITIES,
                page=first,
                number=draft.number,
                printed="",
                message="no speciality was read",
            ),
        )
    return VakJournal(
        number=draft.number,
        pages=tuple(draft.pages),
        title=title.title,
        issn_printed=flatten("\n".join(draft.issns)),
        issns=issns.issns,
        groups=groups,
    )


def _group(group: _Group, number: int, warnings: list[ParseWarning]) -> SpecialityGroup:
    specialities = read_specialities(flatten("\n".join(group.texts)))
    warnings.extend(_warnings(specialities.findings, group.page, number))
    printed = flatten(group.dates)
    if not printed:
        if specialities.specialities:
            warnings.extend(
                _warnings(
                    [
                        Finding(
                            WarningCode.DATE_UNRECOGNIZED,
                            "",
                            "a group without a date",
                        ),
                    ],
                    group.page,
                    number,
                ),
            )
        return SpecialityGroup(
            dates_printed="",
            included=None,
            excluded=None,
            specialities=specialities.specialities,
        )
    dates = read_dates(printed)
    if dates.finding is not None:
        warnings.extend(_warnings([dates.finding], group.page, number))
    return SpecialityGroup(
        dates_printed=printed,
        included=dates.included,
        excluded=dates.excluded,
        specialities=specialities.specialities,
    )


def _warnings(
    findings: Iterable[Finding],
    page: int,
    number: int,
) -> list[ParseWarning]:
    return [
        ParseWarning(
            code=finding.code,
            page=page,
            number=number,
            printed=finding.printed,
            message=finding.message,
        )
        for finding in findings
    ]


def _unrecognized(row: Row) -> ParseWarning:
    printed = " | ".join(
        flatten(cell)
        for cell in (row.number, row.title, row.issn, row.specialities, row.dates)
    )
    return ParseWarning(
        code=WarningCode.ROW_UNRECOGNIZED,
        page=row.page,
        number=None,
        printed=printed,
        message="a row that belongs to no journal",
    )


def _numbering(numbers: list[int]) -> list[ParseWarning]:
    expected = list(range(1, len(numbers) + 1))
    if numbers == expected:
        return []
    missing = sorted(set(expected) - set(numbers))
    repeated = sorted(number for number, seen in Counter(numbers).items() if seen > 1)
    shown = f"missing {missing[:20]}, repeated {repeated[:20]}"
    message = f"numbers are not 1..{len(numbers)} in order: {shown}"
    return [
        ParseWarning(
            code=WarningCode.NUMBERING_GAP,
            page=None,
            number=None,
            printed="",
            message=message,
        ),
    ]
