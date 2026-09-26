"""The title cell: the title, its translation into Russian and its former titles."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vld.vak.models import FormerTitle, VakTitle, WarningCode

from ._dates import parse_day
from ._finding import Finding
from ._issn import find_issns

# «(до 22.12.2020 [г.] наименование [издания] в Перечне «…» [, ISSN …])»; the list
# also prints «До», «наимиенование», «Перчне», «г. .», and forgets the closing bracket.
_FORMER = re.compile(
    r"""
    \(\s*до\s+(?P<until>\d{1,2}\.\d{1,2}\.\d{4})\s*(?:г\s*\.?)?[\s.]*
    наим\w*(?:\s+издания)?\s+в\s+Пер\w*\s*
    (?:
        # With an ISSN the title runs to it, brackets inside the title included;
        # the next «(до …» is never crossed.
        (?P<title>(?:(?!\(\s*до\s+\d).)*?)[,;]?\s*ISSN\s*
        (?P<issns>(?:\d{4}\s*[-‐‑–—]?\s*\d{3}[\dXxХх][,;\s]*)+)[»"”\s]*
        # Without one it runs to the first closing bracket.
        | (?P<bare>[^)]*?)
    )
    \s*(?P<close>\)|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)
# «(перевод наименования на государственный язык Российской Федерации: …)»; the
# list also prints «названия» and drops the colon.
_TRANSLATION = re.compile(
    r"""
    \(\s*перевод\s+(?:наим|назв)\w*\s+на\s+государственный\s+язык
    \s+Российской\s+Федерации\s*:?\s*(?P<title>.*?)\s*(?P<close>\)|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)
# What a bracket of ours says; a bracket that says it but did not parse is reported.
_OURS = re.compile(r"наименовани|перевод|ISSN", re.IGNORECASE)
_QUOTES = '«»"“”„ '


@dataclass(frozen=True, slots=True)
class TitleCell:
    """What the title cell gave.

    Attributes:
        title: VakTitle - The title taken apart.
        findings: tuple[Finding, ...] - Repairs and doubts.

    """

    title: VakTitle
    findings: tuple[Finding, ...]


def read_title(printed: str) -> TitleCell:
    """Take the parsed brackets out of a title; keep every other bracket in it.

    Brackets that are not a translation or a former title, such as «Abyss (Вопросы
    философии…)», are part of the title and stay in `main`.

    Args:
        printed: str - The title cells of a journal, flattened into one line.

    Returns:
        TitleCell - The title and the findings.

    """
    findings: list[Finding] = []
    former: list[FormerTitle] = []
    translation: str | None = None
    main = printed
    for found in list(_FORMER.finditer(printed)):
        former.append(
            FormerTitle(
                until=parse_day(found.group("until")),
                title=(found.group("title") or found.group("bare") or "").strip(
                    _QUOTES + ",;",
                ),
                issns=find_issns(found.group("issns") or ""),
            ),
        )
        main = main.replace(found.group(0), " ")
        findings.extend(_unclosed(found))
        findings.extend(_unread(found))
    found = _TRANSLATION.search(main)
    if found is not None:
        translation = found.group("title").strip(_QUOTES)
        main = main.replace(found.group(0), " ")
        findings.extend(_unclosed(found))
    main = re.sub(r"\s+", " ", main).strip()
    brackets: list[str] = re.findall(r"\([^()]*\)", main)
    if main.count("(") != main.count(")") or any(map(_OURS.search, brackets)):
        findings.append(
            Finding(WarningCode.TITLE_UNPARSED, printed, "a bracket left unparsed"),
        )
    title = VakTitle(
        printed=printed,
        main=main,
        translation=translation,
        former=tuple(former),
    )
    return TitleCell(title, tuple(findings))


def _unclosed(found: re.Match[str]) -> list[Finding]:
    if found.group("close"):
        return []
    return [
        Finding(
            WarningCode.TITLE_REPAIRED,
            found.group(0),
            "bracket closed at the end",
        ),
    ]


def _unread(found: re.Match[str]) -> list[Finding]:
    if parse_day(found.group("until")) is None:
        return [
            Finding(WarningCode.TITLE_UNPARSED, found.group(0), "the date is no date"),
        ]
    if "ISSN" in (found.group("bare") or "").upper():
        return [Finding(WarningCode.TITLE_UNPARSED, found.group(0), "an ISSN not read")]
    return []
