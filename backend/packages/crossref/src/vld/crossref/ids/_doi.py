"""DOI in any form a person pastes, reduced to the form Crossref answers with."""

from __future__ import annotations

import re
from urllib.parse import unquote

from vld.crossref.errors import CrossrefQueryError

_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)
_DOI = re.compile(r"10\.\d+(?:\.\d+)*/\S+")


def normalize_doi(value: str) -> str:
    """Reduce a DOI to `10.<registrant>/<suffix>` in lower case.

    Accepts a bare DOI, `doi:` and the `doi.org` and `dx.doi.org` links,
    percent-encoded or not.

    Args:
        value: str - DOI as typed or copied.

    Returns:
        str - The DOI, lower-cased (DOIs are case-insensitive).

    Raises:
        CrossrefQueryError: If the value is not a DOI.

    """
    text = value.strip()
    lowered = text.lower()
    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    doi = unquote(text).strip().lower()
    if not _DOI.fullmatch(doi):
        msg = f"not a DOI: {value!r}"
        raise CrossrefQueryError(msg)
    return doi
