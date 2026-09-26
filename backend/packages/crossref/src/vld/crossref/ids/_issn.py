"""ISSN reduced to `NNNN-NNNC` and checked by its check digit."""

from __future__ import annotations

import re

from vld.crossref.errors import CrossrefQueryError

_COMPACT = re.compile(r"\d{7}[\dX]")
_MODULUS = 11
_TEN = 10


def normalize_issn(value: str) -> str:
    """Reduce an ISSN to `NNNN-NNNC` and check its check character.

    Args:
        value: str - ISSN with or without a hyphen, spaces or a lower-case `x`.

    Returns:
        str - The ISSN as `NNNN-NNNC`.

    Raises:
        CrossrefQueryError: If the value is not an ISSN or its check digit is wrong.

    """
    compact = re.sub(r"[\s-]", "", value).upper()
    if not _COMPACT.fullmatch(compact):
        msg = f"not an ISSN: {value!r}"
        raise CrossrefQueryError(msg)
    weighted = sum(
        int(digit) * weight
        for digit, weight in zip(compact[:7], range(8, 1, -1), strict=True)
    )
    check = (_MODULUS - weighted % _MODULUS) % _MODULUS
    expected = "X" if check == _TEN else str(check)
    if compact[7] != expected:
        msg = f"wrong ISSN check character: {value!r}"
        raise CrossrefQueryError(msg)
    return f"{compact[:4]}-{compact[4:]}"
