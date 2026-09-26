"""The specialities of a group: split at each code, the branch read from its bracket."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vld.vak.models import Speciality, WarningCode

from ._branches import CANONICAL, branch_of_name, read_branches
from ._finding import Finding

# A code «5.9.5.», «5.9.8 .» or «10.02.01 –», or a code missing its dot before the name.
_CODE = re.compile(
    r"(?<![\d.])(\d{1,2}\.\d{1,2}\.\d{1,2})(?:\s*\.\s*|\s*[–—-]\s*|\s+(?=[А-ЯЁа-яёA-Za-z]))",
)
_TRAILING = " ,;."
# A code the split missed: its speciality is merged into the one before.
_CODE_INSIDE = re.compile(r"\d{1,2}\.\d{1,2}\.\d{1,2}")
_LAST_BRACKET = re.compile(r"\(([^()]*)\)\s*$")


@dataclass(frozen=True, slots=True)
class SpecialityCell:
    """What the text of a group gave.

    Attributes:
        specialities: tuple[Speciality, ...] - In print order.
        findings: tuple[Finding, ...] - Repairs and doubts.

    """

    specialities: tuple[Speciality, ...]
    findings: tuple[Finding, ...]


def read_specialities(text: str) -> SpecialityCell:
    """Split the flattened text of a group into specialities.

    Args:
        text: str - The speciality cells of a group, flattened into one line.

    Returns:
        SpecialityCell - The specialities and the findings.

    """
    codes = list(_CODE.finditer(text))
    findings: list[Finding] = []
    lead = text[: codes[0].start()] if codes else text
    if lead.strip(_TRAILING):
        findings.append(
            Finding(
                WarningCode.SPECIALITY_UNRECOGNIZED,
                lead.strip(),
                "text without a code",
            ),
        )
    specialities: list[Speciality] = []
    for index, code in enumerate(codes):
        end = codes[index + 1].start() if index + 1 < len(codes) else len(text)
        printed = text[code.start() : end].strip(_TRAILING)
        body = text[code.end() : end].strip(_TRAILING)
        read, found = _speciality(code.group(1), body, printed)
        specialities.extend(read)
        findings.extend(found)
        findings.extend(_merged(read[0].name, printed))
    return SpecialityCell(tuple(specialities), tuple(findings))


def _speciality(
    code: str,
    body: str,
    printed: str,
) -> tuple[list[Speciality], list[Finding]]:
    opening = body.rfind("(")
    if opening == -1:
        branch = branch_of_name(body)
        if branch is not None:
            return [
                Speciality(code=code, name=body, branch=branch, printed=printed),
            ], []
        for known, phrase in CANONICAL.items():
            if body.endswith(f" {phrase})"):
                name = body.removesuffix(f"{phrase})").strip(_TRAILING)
                repaired = Finding(
                    WarningCode.BRANCH_REPAIRED,
                    printed,
                    "branch bracket not opened",
                )
                return [
                    Speciality(code=code, name=name, branch=known, printed=printed),
                ], [repaired]
        missing = Finding(WarningCode.BRANCH_MISSING, printed, "no branch bracket")
        return [Speciality(code=code, name=body, branch=None, printed=printed)], [
            missing,
        ]
    name = body[:opening].strip(_TRAILING)
    inside = body[opening + 1 :]
    closed = inside.endswith(")")
    reading = read_branches(inside.replace(")", "").strip())
    findings = [] if reading.finding is None else [reading.finding]
    if not closed and reading.branches and reading.finding is None:
        findings.append(
            Finding(WarningCode.BRANCH_REPAIRED, printed, "branch bracket not closed"),
        )
    if not reading.branches:
        return [
            Speciality(code=code, name=name, branch=None, printed=printed),
        ], findings
    return [
        Speciality(code=code, name=name, branch=branch, printed=printed)
        for branch in reading.branches
    ], findings


def _merged(name: str, printed: str) -> list[Finding]:
    if _CODE_INSIDE.search(name):
        return [
            Finding(
                WarningCode.SPECIALITY_UNRECOGNIZED,
                printed,
                "a code inside the name",
            ),
        ]
    bracket = _LAST_BRACKET.search(name)
    if bracket is not None and read_branches(bracket.group(1)).branches:
        return [
            Finding(
                WarningCode.SPECIALITY_UNRECOGNIZED,
                printed,
                "two branch brackets",
            ),
        ]
    return []
