"""Nineteen real pages of the list of 15.09.2026, one per quirk the parser must survive.

`fixtures/sample.pdf` is cut by `fixtures/cut_pages.py`; its pages are not contiguous,
so the first rows of a page may continue a journal from a page left out and land in
the last journal of the page before. The assertions below name journals whose rows
are all on the pages kept.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from datetime import date
from functools import cache
from pathlib import Path

from vld.vak.models import ScienceBranch, VakJournal, VakList, WarningCode
from vld.vak.parser import parse

FIXTURES = Path(__file__).parent / "fixtures"
PACKAGE = Path(__file__).parents[1]


@cache
def _sample() -> VakList:
    return parse((FIXTURES / "sample.pdf").read_bytes())


def _journal(number: int) -> VakJournal:
    return next(journal for journal in _sample().journals if journal.number == number)


def _codes(number: int) -> list[WarningCode]:
    return [warning.code for warning in _sample().warnings if warning.number == number]


def test_the_parse_equals_the_expected_json() -> None:
    """Every journal and warning of the sample is what sample.json holds."""
    expected = (FIXTURES / "sample.json").read_text(encoding="utf-8")

    actual = _sample().model_dump_json(indent=2, exclude={"parser_version"}) + "\n"

    assert json.loads(actual) == json.loads(expected)


def test_the_version_guard() -> None:
    """A change in what the parser reads is a new version of vld-vak."""
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    project = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))
    digest = hashlib.sha256((FIXTURES / "sample.json").read_bytes()).hexdigest()

    assert manifest["sample_sha256"] == digest, (
        "sample.json changed: the parser reads the list differently now. Bump the "
        "version of vld-vak and put it and this hash into manifest.json: "
        f"{digest}"
    )
    assert manifest["parser_version"] == project["project"]["version"], (
        "manifest.json names another version of vld-vak than pyproject.toml"
    )


def test_the_edition_and_the_pages() -> None:
    """The edition date comes from page 1, the page count from the file."""
    assert (_sample().edition_date, _sample().page_count) == (date(2026, 9, 15), 19)


def test_translation_and_former_title_across_pages_1_and_2() -> None:
    """Journal 3: a translation and a former ISSN in a title cut by page 1."""
    journal = _journal(3)

    assert journal.pages == (1, 2)
    assert journal.title.main == "Acta biomedica scientifica"
    assert journal.title.translation == "Научный биомедицинский журнал"
    assert [(former.until, former.issns) for former in journal.title.former] == [
        (date(2017, 10, 2), ("1811-0649",)),
    ]


def test_a_journal_across_a_page_break_keeps_its_groups() -> None:
    """Journal 6: three date groups on pages 3 and 4 stay one journal."""
    journal = _journal(6)

    assert journal.pages == (3, 4)
    assert [(group.included, group.excluded) for group in journal.groups] == [
        (date(2018, 12, 28), date(2022, 10, 16)),
        (date(2022, 2, 1), None),
        (date(2023, 3, 7), None),
    ]


def test_a_cyrillic_check_letter() -> None:
    """Journal 9 prints «1026-955Х» with a Cyrillic letter."""
    assert _journal(9).issns == ("1026-955X",)
    assert _codes(9) == [WarningCode.ISSN_REPAIRED]


def test_two_issns_in_one_cell() -> None:
    """Journal 40 prints a Cyrillic and a Latin ISSN in one cell."""
    assert _journal(40).issns == ("1811-833X", "2311-7133")


def test_a_broken_issn() -> None:
    """Journal 193 prints «1997 - 4868»."""
    assert _journal(193).issns == ("1997-4868",)
    assert WarningCode.ISSN_REPAIRED in _codes(193)


def test_a_wrong_check_digit() -> None:
    """Journal 409 prints an ISSN whose check digit is wrong: kept."""
    assert _journal(409).issns == ("1996-4741",)
    assert _codes(409) == [WarningCode.ISSN_CHECKSUM]


def test_a_journal_without_an_issn() -> None:
    """Journal 263 has an empty ISSN cell."""
    assert _journal(263).issns == ()
    assert WarningCode.ISSN_MISSING in _codes(263)


def test_short_rulings_inside_a_column_do_not_move_the_issns() -> None:
    """Page 56 of the list draws short lines in the title column."""
    assert [_journal(number).issns for number in (149, 150)] == [
        ("2415-8720",),
        ("2500-4247",),
    ]


def test_a_page_with_other_long_rulings_is_reported_and_still_read() -> None:
    """Page 832 of the list has other long rulings: reported, read by the bounds."""
    shifts = [
        warning.page
        for warning in _sample().warnings
        if warning.code is WarningCode.COLUMN_SHIFT
    ]

    assert shifts == [17]
    assert _journal(2015).issns == ("2070-0970",)


def test_two_branches_in_one_bracket() -> None:
    """Journal 263 lists 5.7.8 for two branches in one bracket."""
    pairs = [
        (speciality.code, speciality.branch)
        for group in _journal(263).groups
        for speciality in group.specialities
        if speciality.code == "5.7.8"
    ]

    assert pairs == [
        ("5.7.8", ScienceBranch.PHILOSOPHY),
        ("5.7.8", ScienceBranch.HISTORY),
    ]


def test_a_whole_branch_as_a_speciality() -> None:
    """Journal 215 prints «6.0.0 военные науки»."""
    specialities = [
        speciality
        for group in _journal(215).groups
        for speciality in group.specialities
    ]

    assert [(speciality.code, speciality.branch) for speciality in specialities] == [
        ("6.0.0", ScienceBranch.MILITARY),
    ]


def test_a_branch_bracket_the_list_did_not_open() -> None:
    """Journals 42 and 2051 print a branch with no opening bracket."""
    assert _codes(42) == [WarningCode.BRANCH_REPAIRED]
    assert _codes(2051) == [WarningCode.BRANCH_REPAIRED]


def test_an_unknown_branch() -> None:
    """Journal 1555 prints «медицинские е науки»."""
    assert _codes(1555) == [WarningCode.BRANCH_UNKNOWN]


def test_date_misprints() -> None:
    """Journal 11 prints «с 01.022022», journal 2397 «с 01.02.202»."""
    assert _journal(11).groups[1].included == date(2022, 2, 1)
    assert _codes(11) == [WarningCode.DATE_REPAIRED]
    assert _journal(2397).groups[0].included is None
    assert _codes(2397) == [WarningCode.DATE_UNRECOGNIZED]


def test_a_title_bracket_left_open_and_one_that_does_not_parse() -> None:
    """Journal 66 leaves a bracket open, journal 156 prints the year 20223."""
    assert _codes(66) == [WarningCode.TITLE_REPAIRED]
    assert _codes(156) == [WarningCode.TITLE_UNPARSED]


def test_numbers_left_out_by_the_cut_are_reported() -> None:
    """The cut leaves numbers out, and the parser says so once."""
    [gap] = [
        warning
        for warning in _sample().warnings
        if warning.code is WarningCode.NUMBERING_GAP
    ]

    assert gap.page is None
