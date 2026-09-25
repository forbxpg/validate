"""Numbered page with `total`, for lists a person pages through."""

from __future__ import annotations

from typing import TypeVar

from fastapi import Query
from fastapi_pagination.customization import CustomizedPage, UseName, UseParamsFields
from fastapi_pagination.limit_offset import LimitOffsetPage

from ._limits import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE

T = TypeVar("T")

TablePage = CustomizedPage[
    LimitOffsetPage[T],
    UseParamsFields(
        limit=Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        offset=Query(0, ge=0, le=MAX_OFFSET),
    ),
    UseName("TablePage"),
]
"""`limit`/`offset` page with `total`: journals, specialities, staff tables."""
