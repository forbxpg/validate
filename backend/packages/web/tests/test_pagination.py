"""The table page: its bounds, its `total`, and its fit to the core protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi_pagination.limit_offset import LimitOffsetPage, LimitOffsetParams

from vld.core.pagination import Page, PageParams
from vld.web.pagination import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE, TablePage

if TYPE_CHECKING:
    from pydantic import BaseModel


def _params_type() -> type[BaseModel]:
    return cast("type[BaseModel]", TablePage.__params_type__)  # pyright: ignore[reportAttributeAccessIssue]


def _upper_bound(field: str) -> object:
    metadata = _params_type().model_fields[field].metadata
    return next(getattr(item, "le", None) for item in metadata if hasattr(item, "le"))


def test_the_page_size_defaults_to_the_shared_size() -> None:
    """One page size policy for the whole API."""
    assert _params_type().model_fields["limit"].default == DEFAULT_PAGE_SIZE


def test_the_page_size_is_bounded_from_above() -> None:
    """A response must not grow together with the catalogue."""
    assert _upper_bound("limit") == MAX_PAGE_SIZE


def test_the_offset_is_bounded_from_above() -> None:
    """A deep offset makes the database skip rows one by one."""
    assert _upper_bound("offset") == MAX_OFFSET


def test_the_table_page_serialises_total() -> None:
    """A person paging through journals sees how many there are."""
    page = TablePage[int](items=[1], total=1, limit=1, offset=0)  # pyright: ignore[reportCallIssue]

    assert cast("BaseModel", page).model_dump()["total"] == 1


def test_the_library_types_satisfy_the_core_protocols() -> None:
    """Core stays free of the library: the fit is structural, not inherited."""
    page = LimitOffsetPage[int].model_construct(items=[1], total=1, limit=10, offset=0)

    assert isinstance(LimitOffsetParams(), PageParams)
    assert isinstance(page, Page)
    assert not isinstance(object(), PageParams)
    assert not isinstance(object(), Page)
