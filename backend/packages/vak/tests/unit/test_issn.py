"""ISSN cells: every form the list prints, normalized, never dropped."""

from __future__ import annotations

import pytest

from vld.vak.models import WarningCode
from vld.vak.parser._issn import find_issns, has_valid_check_digit, read_issns


def _codes(cell: str) -> list[WarningCode]:
    return [finding.code for finding in read_issns(cell).findings]


def test_a_clean_issn_passes_without_a_finding() -> None:
    """A canonical ISSN is taken as it is."""
    cell = read_issns("2587-7534")

    assert cell.issns == ("2587-7534",)
    assert cell.findings == ()


def test_every_issn_of_a_cell_is_kept_in_print_order() -> None:
    """Two ISSNs of a cell stay two, in their order."""
    assert read_issns("2308-944X\n2311-0279").issns == ("2308-944X", "2311-0279")


@pytest.mark.parametrize("cell", ["2308-944X,\n2311-0279", "2308-944X;\n2311-0279"])
def test_separators_between_issns_are_not_text(cell: str) -> None:
    """Commas and semicolons between ISSNs are no stray text."""
    assert _codes(cell) == []


@pytest.mark.parametrize(
    ("cell", "issn"),
    [
        ("1811-833Х", "1811-833X"),
        ("1811-833х", "1811-833X"),
        ("1811-833x", "1811-833X"),
        ("1997 - 4868", "1997-4868"),
        ("1997\n-\n4868", "1997-4868"),
        ("1997–4868", "1997-4868"),
    ],
)
def test_a_misprinted_issn_is_repaired_and_reported(cell: str, issn: str) -> None:
    """A Cyrillic letter, spaces or another dash are repaired and reported."""
    read = read_issns(cell)

    assert read.issns == (issn,)
    assert [finding.code for finding in read.findings] == [WarningCode.ISSN_REPAIRED]


def test_a_wrong_check_digit_is_kept_and_reported() -> None:
    """A wrong check digit is how VAK knows the journal: kept."""
    read = read_issns("1996-4741")

    assert read.issns == ("1996-4741",)
    assert [finding.code for finding in read.findings] == [WarningCode.ISSN_CHECKSUM]


def test_an_empty_cell_is_reported() -> None:
    """An empty cell gives no ISSN and says so."""
    assert _codes("") == [WarningCode.ISSN_MISSING]


def test_text_that_is_no_issn_is_reported_and_kept_out_of_the_issns() -> None:
    """Seven digits are no ISSN."""
    read = read_issns("224-9877")

    assert read.issns == ()
    assert [finding.code for finding in read.findings] == [
        WarningCode.ISSN_UNRECOGNIZED,
    ]


def test_an_issn_in_brackets_is_an_issn() -> None:
    """An ISSN in brackets after another one is kept too, the brackets are no text."""
    read = read_issns("2713-1106\n(2413-5399)")

    assert read.issns == ("2713-1106", "2413-5399")
    assert read.findings == ()


@pytest.mark.parametrize(
    ("issn", "valid"),
    [
        ("2587-7534", True),
        ("2308-944X", True),
        ("1996-4741", False),
        ("2308-9441", False),
    ],
)
def test_the_check_digit(issn: str, *, valid: bool) -> None:
    """The mod 11 check of ISSN, X standing for ten."""
    assert has_valid_check_digit(issn) is valid


def test_issns_are_found_in_running_text() -> None:
    """The ISSNs of a former title bracket are found."""
    assert find_issns("ISSN 2072-8514, 2310-7235)") == ("2072-8514", "2310-7235")
