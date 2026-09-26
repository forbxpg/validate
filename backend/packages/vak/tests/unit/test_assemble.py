"""The state machine over rows: journals, groups, continuations, numbering."""

from __future__ import annotations

from datetime import date

from vld.vak.models import ScienceBranch, WarningCode
from vld.vak.parser._assemble import assemble
from vld.vak.parser._extract import Row

PHILOLOGY = "5.9.5. Русский язык. Языки народов России (филологические\nнауки)"
HISTORY = "5.6.1. Отечественная история (исторические науки)"


def _row(page: int = 1, **cells: str) -> Row:
    return Row(
        page,
        cells.get("number", ""),
        cells.get("title", ""),
        cells.get("issn", ""),
        cells.get("specialities", ""),
        cells.get("dates", ""),
    )


def _codes(rows: list[Row]) -> list[WarningCode]:
    return [warning.code for warning in assemble(rows).warnings]


def test_a_numbered_row_is_a_journal() -> None:
    """A row with a number is a journal with its first group."""
    [journal] = assemble([
        _row(
            number="1.",
            title="Abyss",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
    ]).journals

    assert (journal.number, journal.pages, journal.issns) == (1, (1,), ("2587-7534",))
    [group] = journal.groups
    assert (group.included, group.excluded) == (date(2022, 2, 1), None)
    assert [
        (speciality.code, speciality.branch) for speciality in group.specialities
    ] == [
        ("5.9.5", ScienceBranch.PHILOLOGY),
    ]


def test_a_date_cell_starts_a_group_and_an_empty_one_continues_it() -> None:
    """A speciality cut across rows is joined in its group."""
    rows = [
        _row(
            number="1.",
            title="Abyss",
            issn="2587-7534",
            specialities="10.02.01 – Русский язык",
            dates="с 28.12.2018\nпо 16.10.2022",
        ),
        _row(specialities="(филологические науки)"),
        _row(specialities=PHILOLOGY, dates="с 01.02.2022"),
    ]

    groups = assemble(rows).journals[0].groups

    assert [(group.included, group.excluded) for group in groups] == [
        (date(2018, 12, 28), date(2022, 10, 16)),
        (date(2022, 2, 1), None),
    ]
    assert groups[0].specialities[0].name == "Русский язык"
    assert groups[0].specialities[0].branch is ScienceBranch.PHILOLOGY


def test_a_journal_continues_across_a_page_break() -> None:
    """Rows on the next page belong to the journal above."""
    rows = [
        _row(
            page=3,
            number="6.",
            title="Advanced Engineering\nResearch (до 22.12.2020",
            issn="2687-1653",
            specialities=HISTORY,
            dates="с 01.02.2022",
        ),
        _row(
            page=4,
            title="наименование в Перечне «Вестник ДГТУ» ISSN 1992-5980)",
            specialities=PHILOLOGY,
            dates="с 07.03.2023",
        ),
    ]

    [journal] = assemble(rows).journals

    assert journal.pages == (3, 4)
    assert journal.title.main == "Advanced Engineering Research"
    assert journal.title.former[0].issns == ("1992-5980",)
    assert len(journal.groups) == 2


def test_a_row_before_any_journal_is_reported() -> None:
    """A row with nothing to continue is reported."""
    rows = [
        _row(specialities=HISTORY),
        _row(
            number="1.",
            title="Abyss",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
    ]

    assert _codes(rows) == [WarningCode.ROW_UNRECOGNIZED]


def test_a_number_cell_that_is_no_number_is_reported() -> None:
    """Text in the number column is not a journal."""
    rows = [
        _row(
            number="1.",
            title="Abyss",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
        _row(number="примечание", title="текст"),
    ]

    assert _codes(rows) == [WarningCode.ROW_UNRECOGNIZED]


def test_empty_rows_are_skipped() -> None:
    """Empty rows say nothing."""
    rows = [
        _row(),
        _row(
            number="1.",
            title="Abyss",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
        _row(page=2),
    ]

    assert _codes(rows) == []


def test_a_journal_without_specialities_is_reported() -> None:
    """A journal with no speciality is kept and reported."""
    rows = [_row(number="1.", title="Abyss", issn="2587-7534")]

    assert _codes(rows) == [WarningCode.JOURNAL_WITHOUT_SPECIALITIES]


def test_a_group_without_a_date_is_reported() -> None:
    """Specialities with no date cell are kept and reported."""
    rows = [_row(number="1.", title="Abyss", issn="2587-7534", specialities=PHILOLOGY)]

    assert _codes(rows) == [WarningCode.DATE_UNRECOGNIZED]


def test_a_cell_warning_carries_the_page_and_the_journal() -> None:
    """A warning names the page and the journal it is about."""
    rows = [
        _row(
            page=7,
            number="1.",
            title="FOCUS",
            issn="2713-0177",
            specialities=PHILOLOGY,
            dates="с 01.022022",
        ),
    ]

    [warning] = assemble(rows).warnings

    assert (warning.code, warning.page, warning.number) == (
        WarningCode.DATE_REPAIRED,
        7,
        1,
    )


def test_numbers_that_skip_are_reported_once_for_the_document() -> None:
    """A skipped number is one document warning."""
    rows = [
        _row(
            number="1.",
            title="A",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
        _row(
            number="3.",
            title="B",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
    ]

    [warning] = assemble(rows).warnings

    assert (warning.code, warning.page, warning.number) == (
        WarningCode.NUMBERING_GAP,
        None,
        None,
    )
    assert "missing [2]" in warning.message


def test_numbers_that_repeat_are_reported() -> None:
    """A number read twice is reported."""
    rows = [
        _row(
            number="1.",
            title="A",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
        _row(
            number="1.",
            title="B",
            issn="2587-7534",
            specialities=PHILOLOGY,
            dates="с 01.02.2022",
        ),
    ]

    assert _codes(rows) == [WarningCode.NUMBERING_GAP]
