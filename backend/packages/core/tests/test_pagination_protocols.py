"""Протоколы страницы совместимы с библиотекой структурно, без наследования."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi_pagination.cursor import CursorPage, CursorParams
from fastapi_pagination.limit_offset import LimitOffsetPage, LimitOffsetParams

from vld.core.pagination import Page, PageParams

if TYPE_CHECKING:
    from collections.abc import Sequence


def test_library_params_satisfy_the_params_protocol() -> None:
    assert isinstance(CursorParams(), PageParams)
    assert isinstance(LimitOffsetParams(), PageParams)


def test_library_pages_satisfy_the_page_protocol() -> None:
    cursor_page: CursorPage[int] = CursorPage[int].model_construct(
        items=[1, 2], total=2
    )
    table_page: LimitOffsetPage[int] = LimitOffsetPage[int].model_construct(
        items=[1, 2], total=2, limit=10, offset=0
    )

    assert isinstance(cursor_page, Page)
    assert isinstance(table_page, Page)


def test_the_protocols_reject_something_shaped_wrong() -> None:
    assert not isinstance(object(), PageParams)
    assert not isinstance(object(), Page)


def test_the_page_protocol_does_not_demand_total() -> None:
    class _OnlyItems:
        items: Sequence[int] = (1, 2)

    assert isinstance(_OnlyItems(), Page)
