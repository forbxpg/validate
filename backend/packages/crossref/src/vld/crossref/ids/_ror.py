"""ROR id reduced to its nine characters."""

from __future__ import annotations

import re

from vld.crossref.errors import CrossrefQueryError

_PREFIXES = ("https://ror.org/", "http://ror.org/", "ror.org/")
_ROR = re.compile(r"0[a-z0-9]{6}\d{2}")


def normalize_ror(value: str) -> str:
    """Reduce a ROR id to its nine characters, such as ``05qwgg493``.

    Args:
        value: str - The id, bare or as a ``ror.org`` link.

    Returns:
        str - The nine-character id in lower case.

    Raises:
        CrossrefQueryError: If the value is not a ROR id.

    """
    text = value.strip().lower()
    for prefix in _PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if not _ROR.fullmatch(text):
        msg = f"not a ROR id: {value!r}"
        raise CrossrefQueryError(msg)
    return text
