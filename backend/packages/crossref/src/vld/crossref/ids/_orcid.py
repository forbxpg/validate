"""ORCID iD reduced to ``NNNN-NNNN-NNNN-NNNC`` and checked by ISO 7064 MOD 11-2."""

from __future__ import annotations

import re

from vld.crossref.errors import CrossrefQueryError

_PREFIXES = ("https://orcid.org/", "http://orcid.org/", "orcid.org/")
_COMPACT = re.compile(r"\d{15}[\dX]")
_MODULUS = 11
_TEN = 10


def normalize_orcid(value: str) -> str:
    """Reduce an ORCID iD to ``NNNN-NNNN-NNNN-NNNC`` and check its check character.

    Args:
        value: str - The iD, bare or as an ``orcid.org`` link.

    Returns:
        str - The iD with hyphens.

    Raises:
        CrossrefQueryError: If the value is not an ORCID iD or its check
            character is wrong.

    """
    text = value.strip()
    lowered = text.lower()
    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    compact = text.replace("-", "").upper()
    if not _COMPACT.fullmatch(compact):
        msg = f"not an ORCID iD: {value!r}"
        raise CrossrefQueryError(msg)
    total = 0
    for digit in compact[:15]:
        total = (total + int(digit)) * 2
    check = (_MODULUS + 1 - total % _MODULUS) % _MODULUS
    expected = "X" if check == _TEN else str(check)
    if compact[15] != expected:
        msg = f"wrong ORCID check character: {value!r}"
        raise CrossrefQueryError(msg)
    return "-".join(compact[i : i + 4] for i in range(0, 16, 4))
