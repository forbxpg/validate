"""Two types of pages: by purpose, not by mechanics."""

from __future__ import annotations

from typing import TypeVar

from fastapi import Query
from fastapi_pagination.cursor import CursorPage
from fastapi_pagination.customization import (
    CustomizedPage,
    UseExcludedFields,
    UseIncludeTotal,
    UseName,
    UseParamsFields,
)
from fastapi_pagination.limit_offset import LimitOffsetPage

from ._limits import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE

T = TypeVar("T")

FeedPage = CustomizedPage[
    CursorPage[T],
    UseIncludeTotal(False),  # ruff: ignore[boolean-positional-value-in-call]
    UseExcludedFields("total"),
    UseParamsFields(size=Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)),
    UseName("FeedPage"),
]
"""Feed: cursor, without `total`, depth is not worth it."""

TablePage = CustomizedPage[
    LimitOffsetPage[T],
    UseParamsFields(
        limit=Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        offset=Query(0, ge=0, le=MAX_OFFSET),
    ),
    UseName("TablePage"),
]
"""Numbered pages with `total` — where the person looks at the volume.

Otherwise the field would remain in the response as `"total": null` in each page.
"""
