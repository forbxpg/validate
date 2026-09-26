"""Title cells: translations and former titles taken out, other brackets kept."""

from __future__ import annotations

from datetime import date

import pytest

from vld.vak.models import FormerTitle, WarningCode
from vld.vak.parser._title import read_title


def _codes(printed: str) -> list[WarningCode]:
    return [finding.code for finding in read_title(printed).findings]


def test_a_plain_title() -> None:
    """A title without brackets is its own main title."""
    title = read_title("Вопросы философии").title

    assert (title.main, title.translation, title.former) == (
        "Вопросы философии",
        None,
        (),
    )


def test_a_bracket_that_is_part_of_the_title_stays() -> None:
    """«Abyss (Вопросы философии…)» is one title."""
    printed = "Abyss (Вопросы философии, политологии и социальной антропологии)"

    assert read_title(printed).title.main == printed
    assert _codes(printed) == []


@pytest.mark.parametrize(
    "printed",
    [
        "Acta medica Eurasica (перевод наименования на государственный язык Российской Федерации: Медицинский вестник Евразии)",
        "Acta medica Eurasica (перевод наименование на государственный язык Российской Федерации: Медицинский вестник Евразии)",
        "Acta medica Eurasica (перевод названия на государственный язык Российской Федерации: Медицинский вестник Евразии)",
        "Acta medica Eurasica (перевод наименования на государственный язык Российской Федерации Медицинский вестник Евразии)",
    ],
)
def test_a_translation_is_taken_out(printed: str) -> None:
    """Every wording of the translation bracket the list uses."""
    title = read_title(printed).title

    assert (title.main, title.translation) == (
        "Acta medica Eurasica",
        "Медицинский вестник Евразии",
    )


@pytest.mark.parametrize(
    ("printed", "former"),
    [
        (
            "Advanced Engineering Research (до 22.12.2020 наименование в Перечне «Вестник Донского государственного технического университета» ISSN 1992-5980)",
            FormerTitle(
                until=date(2020, 12, 22),
                title="Вестник Донского государственного технического университета",
                issns=("1992-5980",),
            ),
        ),
        (
            "Биология (До 09.08.2018 г. наименование в Перечне Вестник Санкт-Петербургского университета. Серия 3. Биология ISSN 1025-8604)",
            FormerTitle(
                until=date(2018, 8, 9),
                title="Вестник Санкт-Петербургского университета. Серия 3. Биология",
                issns=("1025-8604",),
            ),
        ),
        (
            "Психология (до 30.06.2022 наименование в Перечне «Психология», ISSN 2072-8514, 2310-7235)",
            FormerTitle(
                until=date(2022, 6, 30),
                title="Психология",
                issns=("2072-8514", "2310-7235"),
            ),
        ),
        (
            "Медицина (до 18.11.2019 г. . наименование в Перечне «Анналы хирургии» ISSN 2072-8093)",
            FormerTitle(
                until=date(2019, 11, 18),
                title="Анналы хирургии",
                issns=("2072-8093",),
            ),
        ),
        (
            "Скотоводство ( до 03.04.2019 наименование в перечне «Вестник мясного скотоводства (Herald of Beef Cattle Breeding)» ISSN 2079-6250)",
            FormerTitle(
                until=date(2019, 4, 3),
                title="Вестник мясного скотоводства (Herald of Beef Cattle Breeding)",
                issns=("2079-6250",),
            ),
        ),
        (
            "Ремедиум (до 13.1.2022 наименование в перечне «Ремедиум. Журнал о рынке лекарств»)",
            FormerTitle(
                until=date(2022, 1, 13),
                title="Ремедиум. Журнал о рынке лекарств",
                issns=(),
            ),
        ),
        (
            "Вестник АПК (до 14.11.2023 наименование в Перчне «Вестник АПК Ставрополья» ISSN 2222-9345)",
            FormerTitle(
                until=date(2023, 11, 14),
                title="Вестник АПК Ставрополья",
                issns=("2222-9345",),
            ),
        ),
    ],
)
def test_a_former_title_is_taken_out(printed: str, former: FormerTitle) -> None:
    """Every wording of the former title bracket the list uses."""
    read = read_title(printed)

    assert read.title.former == (former,)
    assert "(" not in read.title.main
    assert read.findings == ()


def test_several_former_titles_keep_their_order() -> None:
    """Two renames, each with its ISSN."""
    printed = (
        "Сибирский аэрокосмический журнал (САЖ) "
        "(До 18.06.2021 г. наименование в Перечне «Сибирский журнал науки и технологий (СибЖНТ)» ISSN 2587-6066) "
        "(До 26.01.2018 г. наименование в Перечне «Вестник СибГАУ» ISSN 1816-9724)"
    )

    title = read_title(printed).title

    assert title.main == "Сибирский аэрокосмический журнал (САЖ)"
    assert [former.issns for former in title.former] == [("2587-6066",), ("1816-9724",)]


def test_a_translation_and_a_former_title_together() -> None:
    """Both brackets in one title."""
    printed = (
        "BULLETIN OF ART AND EDUCATION (перевод названия на государственный язык "
        "Российской Федерации: БЮЛЛЕТЕНЬ ИСКУССТВО И ОБРАЗОВАНИЕ) (до 30.09.2025 наименование "
        "в Перечне «BULLETIN OF THE INTERNATIONAL CENTRE OF ART AND EDUCATION» ISSN 2618-6942)"
    )

    title = read_title(printed).title

    assert title.main == "BULLETIN OF ART AND EDUCATION"
    assert title.translation == "БЮЛЛЕТЕНЬ ИСКУССТВО И ОБРАЗОВАНИЕ"
    assert title.former[0].issns == ("2618-6942",)


def test_a_bracket_the_list_forgot_to_close_is_read_and_reported() -> None:
    """A former title running to the end of the cell."""
    printed = "Экономика (до 20.12.2022 наименование в Перечне «Вестник СПбГУ. Серия 5. Экономика»"

    read = read_title(printed)

    assert read.title.main == "Экономика"
    assert read.title.former[0].title == "Вестник СПбГУ. Серия 5. Экономика"
    assert [finding.code for finding in read.findings] == [WarningCode.TITLE_REPAIRED]


def test_a_former_title_bracket_that_does_not_parse_is_reported_and_kept() -> None:
    """A bracket of ours that does not parse stays in the title."""
    printed = "Tempus et Memoria (до 08.02.20223 наименование в Перечне «Известия УрФУ» ISSN 2227-2291)"

    read = read_title(printed)

    assert read.title.main == printed
    assert read.title.former == ()
    assert [finding.code for finding in read.findings] == [WarningCode.TITLE_UNPARSED]


def test_a_former_title_without_an_issn_does_not_reach_into_the_next() -> None:
    """The first rename has no ISSN; its title stops at its own bracket."""
    printed = (
        "Вестник (до 01.01.2019 наименование в Перечне «Первый») "
        "(до 01.01.2020 наименование в Перечне «Второй» ISSN 2587-7534)"
    )

    title = read_title(printed).title

    assert [(former.title, former.issns) for former in title.former] == [
        ("Первый", ()),
        ("Второй", ("2587-7534",)),
    ]


def test_a_stray_quote_after_the_issn_of_an_open_bracket() -> None:
    """Journal 245 ends its former title with «ISSN 1995-1477»» and no bracket."""
    printed = (
        "Амбулаторная хирургия (До 22.03.2022 г. наименование в Перечне "
        "«Стационарозамещающие технологии: Амбулаторная хирургия» ISSN 1995-1477»"
    )

    read = read_title(printed)

    assert read.title.main == "Амбулаторная хирургия"
    assert [(former.title, former.issns) for former in read.title.former] == [
        ("Стационарозамещающие технологии: Амбулаторная хирургия", ("1995-1477",)),
    ]
    assert [finding.code for finding in read.findings] == [WarningCode.TITLE_REPAIRED]


def test_an_issn_left_in_a_former_title_is_reported() -> None:
    """An ISSN the bracket could not read never passes as part of the title."""
    printed = "Вестник (до 01.01.2020 наименование в Перечне «Старый» ISSN 1234)"

    assert [finding.code for finding in read_title(printed).findings] == [
        WarningCode.TITLE_UNPARSED,
    ]


def test_a_former_title_date_the_calendar_does_not_have_is_reported() -> None:
    """«до 31.02.2020» is kept as no date and said so."""
    printed = "Вестник (до 31.02.2020 наименование в Перечне «Старый» ISSN 2587-7534)"

    read = read_title(printed)

    assert read.title.former[0].until is None
    assert [finding.code for finding in read.findings] == [WarningCode.TITLE_UNPARSED]
