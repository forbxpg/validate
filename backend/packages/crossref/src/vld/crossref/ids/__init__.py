"""Identifiers accepted in any common form and reduced to one."""

from __future__ import annotations

from ._doi import normalize_doi
from ._issn import normalize_issn

__all__ = ("normalize_doi", "normalize_issn")
