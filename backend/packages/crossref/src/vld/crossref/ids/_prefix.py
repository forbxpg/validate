"""DOI prefix, the part of a DOI its owner registered."""

from __future__ import annotations

import re

from vld.crossref.errors import CrossrefQueryError

_PREFIX = re.compile(r"10\.\d+(?:\.\d+)*")


def normalize_prefix(value: str) -> str:
    """Check a DOI prefix such as ``10.1103``.

    Args:
        value: str - The prefix.

    Returns:
        str - The prefix without surrounding whitespace.

    Raises:
        CrossrefQueryError: If the value is not a DOI prefix.

    """
    prefix = value.strip()
    if not _PREFIX.fullmatch(prefix):
        msg = f"not a DOI prefix: {value!r}"
        raise CrossrefQueryError(msg)
    return prefix
