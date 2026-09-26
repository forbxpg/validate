"""Speciality text: split at codes of both nomenclatures, branches read."""

from __future__ import annotations

from vld.vak.models import ScienceBranch, WarningCode
from vld.vak.parser._specialities import read_specialities


def _pairs(text: str) -> list[tuple[str, str, ScienceBranch | None]]:
    return [
        (speciality.code, speciality.name, speciality.branch)
        for speciality in read_specialities(text).specialities
    ]


def _codes(text: str) -> list[WarningCode]:
    return [finding.code for finding in read_specialities(text).findings]


def test_new_nomenclature_codes_end_with_a_dot() -> None:
    """«5.6.4.» starts a speciality of the 2021 nomenclature."""
    text = (
        "5.6.4. Этнология, антропология и этнография (исторические науки), "
        "5.7.6. Философия науки и техники (философские науки)"
    )

    assert _pairs(text) == [
        ("5.6.4", "Этнология, антропология и этнография", ScienceBranch.HISTORY),
        ("5.7.6", "Философия науки и техники", ScienceBranch.PHILOSOPHY),
    ]
    assert _codes(text) == []


def test_old_nomenclature_codes_end_with_a_dash() -> None:
    """«10.01.01 –» starts a speciality of the old nomenclature."""
    text = "10.01.01 – Русская литература (филологические науки), 10.02.01 – Русский язык (филологические науки)"

    assert [code for code, _, _ in _pairs(text)] == ["10.01.01", "10.02.01"]


def test_specialities_without_a_comma_between_them_are_split() -> None:
    """The list sometimes forgets the comma: the code still splits."""
    text = "3.2.2. Эпидемиология (медицинские науки) 3.3.3. Патологическая физиология (биологические науки)"

    assert [code for code, _, _ in _pairs(text)] == ["3.2.2", "3.3.3"]


def test_a_code_without_its_dot_still_starts_a_speciality() -> None:
    """«3.2.1 Гигиена» has no dot after the code."""
    assert _pairs("3.2.1 Гигиена (медицинские науки)") == [
        ("3.2.1", "Гигиена", ScienceBranch.MEDICINE),
    ]


def test_a_bracket_inside_the_name_stays_in_the_name() -> None:
    """Only the last bracket is the branch."""
    text = "5.9.6. Языки народов зарубежных стран (с указанием конкретного языка или группы языков) (филологические науки)"

    assert _pairs(text) == [
        (
            "5.9.6",
            "Языки народов зарубежных стран (с указанием конкретного языка или группы языков)",
            ScienceBranch.PHILOLOGY,
        ),
    ]


def test_a_bracket_of_two_branches_gives_one_speciality_per_branch() -> None:
    """One speciality printed for two branches is two specialities."""
    text = "5.7.8. Философская антропология, философия культуры (философские науки, исторические науки)"

    assert [branch for _, _, branch in _pairs(text)] == [
        ScienceBranch.PHILOSOPHY,
        ScienceBranch.HISTORY,
    ]


def test_a_whole_branch_as_a_speciality_is_read() -> None:
    """«6.0.0 военные науки» has no bracket and needs none."""
    assert _pairs("6.0.0 военные науки") == [
        ("6.0.0", "военные науки", ScienceBranch.MILITARY),
    ]


def test_an_unclosed_bracket_is_read_and_reported() -> None:
    """A branch bracket cut before «)» is read and reported."""
    assert _pairs("2.6.4. Обработка металлов давлением (технические науки") == [
        ("2.6.4", "Обработка металлов давлением", ScienceBranch.TECHNICAL),
    ]
    assert _codes("2.6.4. Обработка металлов давлением (технические науки") == [
        WarningCode.BRANCH_REPAIRED,
    ]


def test_an_unopened_bracket_is_read_and_reported() -> None:
    """«Кардиология биологические науки)» is read and reported."""
    text = "3.1.20. Кардиология биологические науки)"

    assert _pairs(text) == [("3.1.20", "Кардиология", ScienceBranch.BIOLOGY)]
    assert _codes(text) == [WarningCode.BRANCH_REPAIRED]


def test_a_speciality_without_a_branch_is_kept_and_reported() -> None:
    """A name cut short keeps its code and has no branch."""
    text = "5.8.4. Физическая культура и"

    assert _pairs(text) == [("5.8.4", "Физическая культура и", None)]
    assert _codes(text) == [WarningCode.BRANCH_MISSING]


def test_text_before_the_first_code_is_reported() -> None:
    """Text before any code belongs to no speciality."""
    assert _codes("наук), 5.9.1. Русская литература (филологические науки)") == [
        WarningCode.SPECIALITY_UNRECOGNIZED,
    ]


def test_the_printed_form_is_kept() -> None:
    """The speciality as printed, trailing comma dropped."""
    [speciality] = read_specialities(
        "5.2.3. Региональная и отраслевая экономика (экономические науки),",
    ).specialities

    assert (
        speciality.printed
        == "5.2.3. Региональная и отраслевая экономика (экономические науки)"
    )
