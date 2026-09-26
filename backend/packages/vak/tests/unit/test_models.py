"""The parse result as a format: written and read back, a foreign version refused."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from vld.vak.models import (
    ParseWarning,
    ScienceBranch,
    Speciality,
    SpecialityGroup,
    VakJournal,
    VakList,
    VakTitle,
    WarningCode,
)


def _list() -> VakList:
    speciality = Speciality(
        code="5.9.5",
        name="Русский язык. Языки народов России",
        branch=ScienceBranch.PHILOLOGY,
        printed="5.9.5. Русский язык. Языки народов России (филологические науки)",
    )
    journal = VakJournal(
        number=1,
        pages=(1, 2),
        title=VakTitle(printed="Abyss", main="Abyss", translation=None, former=()),
        issn_printed="2587-7534",
        issns=("2587-7534",),
        groups=(
            SpecialityGroup(
                dates_printed="с 01.02.2022",
                included=date(2022, 2, 1),
                excluded=None,
                specialities=(speciality,),
            ),
        ),
    )
    warning = ParseWarning(
        code=WarningCode.DATE_REPAIRED,
        page=1,
        number=1,
        printed="с 01.022022",
        message="read as 'с 01.02.2022'",
    )
    return VakList(
        parser_version="0.1.0",
        edition_date=date(2026, 9, 15),
        page_count=1277,
        journals=(journal,),
        warnings=(warning,),
    )


def test_the_json_reads_back_into_the_same_list() -> None:
    """The JSON of a list reads back equal."""
    original = _list()

    assert VakList.model_validate_json(original.model_dump_json()) == original


def test_the_json_names_its_format_version() -> None:
    """The JSON carries its format version."""
    assert '"format_version":1' in _list().model_dump_json()


def test_another_format_version_is_refused() -> None:
    """A JSON of another format version is not read."""
    data = _list().model_dump(mode="json") | {"format_version": 2}

    with pytest.raises(ValidationError):
        VakList.model_validate(data)


def test_an_unknown_field_is_refused() -> None:
    """A field the format does not know is refused."""
    data = _list().model_dump(mode="json") | {"extra": 1}

    with pytest.raises(ValidationError):
        VakList.model_validate(data)


def test_the_result_is_frozen() -> None:
    """A parse result cannot be changed after the fact."""
    result = _list()

    with pytest.raises(ValidationError):
        result.page_count = 1


def test_repair_codes_are_told_apart_from_the_rest() -> None:
    """Exactly the four repair codes count as repairs."""
    repairs = {code for code in WarningCode if code.is_repair}

    assert repairs == {
        WarningCode.ISSN_REPAIRED,
        WarningCode.BRANCH_REPAIRED,
        WarningCode.DATE_REPAIRED,
        WarningCode.TITLE_REPAIRED,
    }
