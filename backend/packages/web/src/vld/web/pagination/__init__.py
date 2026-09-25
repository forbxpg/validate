"""HTTP page type and its bounds."""

from __future__ import annotations

from ._limits import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE
from ._pages import TablePage

__all__ = (
    "DEFAULT_PAGE_SIZE",
    "MAX_OFFSET",
    "MAX_PAGE_SIZE",
    "TablePage",
)
