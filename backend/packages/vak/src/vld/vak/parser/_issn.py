"""ISSNs of a cell: found, normalized, checked, never dropped."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vld.vak.models import WarningCode

from ._finding import Finding, flatten

# Any dash, spaces around it, or none; a Cyrillic «Х» or a lowercase x as the check.
_CANDIDATE = re.compile(r"(?<!\d)(\d{4})(\s*[-‐‑–—]?\s*)(\d{3}[\dXxХх])(?![\dXxХх])")
_SEPARATORS = re.compile(r"[\s,;()]+")
_CHECK_MODULUS = 11
_CHECK_TEN = 10


@dataclass(frozen=True, slots=True)
class IssnCell:
    """What a cell of ISSNs gave.

    Attributes:
        issns: tuple[str, ...] - Normalized ``NNNN-NNNC``, in print order.
        findings: tuple[Finding, ...] - Repairs and doubts.

    """

    issns: tuple[str, ...]
    findings: tuple[Finding, ...]


def read_issns(cell: str) -> IssnCell:
    """Find every ISSN of a cell.

    Args:
        cell: str - The cell as printed.

    Returns:
        IssnCell - The ISSNs and the findings.

    """
    text = flatten(cell)
    if not text:
        return IssnCell((), (Finding(WarningCode.ISSN_MISSING, "", "no ISSN"),))
    issns: list[str] = []
    findings: list[Finding] = []
    for found in _CANDIDATE.finditer(text):
        issn, finding = _normalize(found)
        issns.append(issn)
        if finding is not None:
            findings.append(finding)
        if not has_valid_check_digit(issn):
            findings.append(
                Finding(
                    WarningCode.ISSN_CHECKSUM,
                    issn,
                    "the check digit does not match",
                ),
            )
    rest = _SEPARATORS.sub("", _CANDIDATE.sub("", text))
    if rest:
        findings.append(
            Finding(WarningCode.ISSN_UNRECOGNIZED, text, f"not an ISSN: {rest!r}"),
        )
    return IssnCell(tuple(issns), tuple(findings))


def find_issns(text: str) -> tuple[str, ...]:
    """Find the ISSNs inside running text, such as a former title bracket.

    Args:
        text: str - Text that may mention ISSNs.

    Returns:
        tuple[str, ...] - Normalized ISSNs, in order.

    """
    return tuple(_normalize(found)[0] for found in _CANDIDATE.finditer(text))


def has_valid_check_digit(issn: str) -> bool:
    """Tell whether the last character of an ISSN matches its first seven digits.

    Args:
        issn: str - A normalized ISSN ``NNNN-NNNC``.

    Returns:
        bool - True if the check character is right.

    """
    digits = issn.replace("-", "")
    total = sum(
        int(digit) * weight
        for digit, weight in zip(digits[:7], range(8, 1, -1), strict=True)
    )
    check = (_CHECK_MODULUS - total % _CHECK_MODULUS) % _CHECK_MODULUS
    return digits[7] == ("X" if check == _CHECK_TEN else str(check))


def _normalize(found: re.Match[str]) -> tuple[str, Finding | None]:
    head, dash, tail = found.group(1), found.group(2), found.group(3)
    issn = f"{head}-{tail[:3]}{tail[3].upper().replace('Х', 'X')}"
    if dash == "-" and tail[3] not in "xХх":
        return issn, None
    return issn, Finding(WarningCode.ISSN_REPAIRED, found.group(0), f"read as {issn}")
