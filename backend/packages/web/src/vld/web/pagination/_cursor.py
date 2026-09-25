"""Cursor of the feed carries the order by which it is collected."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from pydantic import BaseModel

    from vld.core.pagination import Page, PageParams


_MARK = "."
_BAD_CURSOR = (
    "Курсор страницы не разобран: он испорчен либо собран для другого "
    "порядка сортировки."
)


def _refuse() -> HTTPException:
    """Отказ по негодному курсору — один текст на оба его вида.

    Returns:
        HTTPException - Готовый отказ с человеческим текстом.

    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=_BAD_CURSOR,
    )


def params_for(order: str, params: PageParams) -> PageParams:
    """Remove the order mark from the cursor, checking that it is its own.

    Args:
        order: str - Order, by which this page is collected.
        params: PageParams - Page parameters from the request.

    Returns:
        PageParams - The same parameters with the cursor without the mark.

    Raises:
        _refuse: if the mark is present but foreign, or absent at all.

    """
    cursor = cast("str | None", getattr(params, "cursor", None))
    if cursor is None:
        return params
    mark, found, rest = cursor.partition(_MARK)
    if not found or mark != order:
        raise _refuse()
    model = cast("BaseModel", cast("object", params))
    return cast("PageParams", cast("object", model.model_copy(update={"cursor": rest})))


def _marked(order: str, cursor: str | None) -> str | None:
    """Attach the order mark to the cursor, leaving it to the client.

    Args:
        order: str - Order of the collected page.
        cursor: str | None - Cursor, issued by the library.

    Returns:
        str | None - Cursor with the mark or ``None``, if it is not.

    """
    return None if cursor is None else f"{order}{_MARK}{cursor}"


async def feed_page_of[T](order: str, page: Awaitable[Page[T]]) -> Page[T]:
    """Collect the page and mark its cursors with our order.

    Args:
        order: str - Order, by which this page is collected.
        page: Awaitable[Page[T]] - Page collection.

    Returns:
        Page[T] - The same page with marked cursors.

    Raises:
        _refuse: if the cursor is not resolved inside the library.

    """
    try:
        built = await page
    except Exception as error:
        raise _refuse() from error
    page_model = cast("BaseModel", cast("object", built))
    marks = {
        name: _marked(order, cast("str | None", getattr(page_model, name)))
        for name in ("next_page", "previous_page", "current_page")
        if hasattr(page_model, name)
    }
    return cast("Page[T]", cast("object", page_model.model_copy(update=marks)))
