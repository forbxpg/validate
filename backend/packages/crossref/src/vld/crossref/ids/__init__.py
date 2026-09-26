"""Identifiers accepted in any common form and reduced to one."""

from __future__ import annotations

from ._doi import normalize_doi
from ._issn import normalize_issn
from ._orcid import normalize_orcid
from ._prefix import normalize_prefix
from ._ror import normalize_ror

__all__ = (
    "normalize_doi",
    "normalize_issn",
    "normalize_orcid",
    "normalize_prefix",
    "normalize_ror",
)
