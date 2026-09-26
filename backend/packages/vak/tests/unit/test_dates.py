"""Date cells: the canonical form, the unambiguous misprints, and the rest."""

from __future__ import annotations

from datetime import date

import pytest

from vld.vak.models import WarningCode
from vld.vak.parser._dates import read_dates


def test_an_included_date() -> None:
    """«с ДД.ММ.ГГГГ» is the included date, nothing to report."""
    cell = read_dates("с 01.02.2022")

    assert (cell.included, cell.excluded, cell.finding) == (
        date(2022, 2, 1),
        None,
        None,
    )


def test_an_included_and_an_excluded_date() -> None:
    """«с … по …» gives both dates."""
    cell = read_dates("с 28.12.2018 по 16.10.2022")

    assert (cell.included, cell.excluded, cell.finding) == (
        date(2018, 12, 28),
        date(2022, 10, 16),
        None,
    )


@pytest.mark.parametrize(
    ("printed", "included", "excluded"),
    [
        ("с 01.022022", date(2022, 2, 1), None),
        ("с 01.022.022", date(2022, 2, 1), None),
        ("С 11.12.2023", date(2023, 12, 11), None),
        ("c 01.02.2022", date(2022, 2, 1), None),
        ("с 2 2 . 1 1 . 2 0 2 2", date(2022, 11, 22), None),
        ("с 01.02.2022.", date(2022, 2, 1), None),
        ("01.02.2022", date(2022, 2, 1), None),
        ("с 12.02.2019 п о 16.10.2022", date(2019, 2, 12), date(2022, 10, 16)),
        ("с 28.12.2018 до 28.02.2023", date(2018, 12, 28), date(2023, 2, 28)),
    ],
)
def test_an_unambiguous_misprint_is_repaired_and_reported(
    printed: str,
    included: date,
    excluded: date | None,
) -> None:
    """Misprints with one reading are repaired, the printed text kept."""
    cell = read_dates(printed)

    assert (cell.included, cell.excluded) == (included, excluded)
    assert cell.finding is not None
    assert cell.finding.code is WarningCode.DATE_REPAIRED
    assert cell.finding.printed == printed


@pytest.mark.parametrize(
    "printed",
    [
        "с 01.02.202",
        "с 01.0.2022",
        "с 32.01.2022",
        "с 01.02.2022 по 01.02.202",
        "5.9.6. Языки",
    ],
)
def test_anything_else_is_reported_without_dates(printed: str) -> None:
    """A cell with more than one reading gives no dates."""
    cell = read_dates(printed)

    assert (cell.included, cell.excluded) == (None, None)
    assert cell.finding is not None
    assert cell.finding.code is WarningCode.DATE_UNRECOGNIZED
