"""Pagination of the monolith: page boundaries and two its types."""

from __future__ import annotations

from ._cursor import feed_page_of, params_for
from ._limits import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE
from ._pages import FeedPage, TablePage

__all__ = (
    "DEFAULT_PAGE_SIZE",
    "MAX_OFFSET",
    "MAX_PAGE_SIZE",
    "FeedPage",
    "TablePage",
    "feed_page_of",
    "params_for",
)
