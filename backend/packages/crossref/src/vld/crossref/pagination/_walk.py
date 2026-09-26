"""Walking a list of any size with the cursor."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from vld.crossref.errors import (
    CrossrefBadRequestError,
    CrossrefCursorExpiredError,
    CrossrefQueryError,
)

from ._page import MAX_ROWS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

    from vld.crossref.transport import Envelope

CURSOR_LIFETIME = timedelta(minutes=5)
"""How long Crossref keeps a cursor between two requests."""


async def _fetch_page(
    fetch: Callable[[Mapping[str, str]], Awaitable[Envelope | None]],
    params: Mapping[str, str],
    cursor: str,
    page_size: int,
) -> Envelope | None:
    """GET one cursor page; a refused later cursor means it expired.

    Args:
        fetch: Callable[[Mapping[str, str]], Awaitable[Envelope | None]] - GETs
            the list.
        params: Mapping[str, str] - Parameters of the query.
        cursor: str - ``*`` or the cursor of the previous page.
        page_size: int - Rows per request.

    Returns:
        Envelope | None - The page, or None on 404.

    Raises:
        CrossrefCursorExpiredError: If Crossref refused a cursor after the first.
        CrossrefBadRequestError: If Crossref refused anything else.

    """
    try:
        return await fetch({**params, "rows": str(page_size), "cursor": cursor})
    except CrossrefBadRequestError as error:
        if cursor != "*" and any("cursor" in p.type for p in error.problems):
            msg = "Crossref refused the cursor"
            raise CrossrefCursorExpiredError(msg, url=error.url) from error
        raise


def check_walk(max_items: int | None, page_size: int) -> None:
    """Refuse walk bounds that cannot work.

    Args:
        max_items: int | None - Most records to yield; None for all.
        page_size: int - Rows per request.

    Raises:
        CrossrefQueryError: If ``max_items`` is negative or ``page_size`` is
            outside 1..1000.

    """
    if max_items is not None and max_items < 0:
        msg = f"max_items must not be negative, got {max_items}"
        raise CrossrefQueryError(msg)
    if not 1 <= page_size <= MAX_ROWS:
        msg = f"page_size must be within 1..{MAX_ROWS}, got {page_size}"
        raise CrossrefQueryError(msg)


async def walk[T](  # ruff: ignore[too-many-arguments] -- shared by every list, all named
    *,
    fetch: Callable[[Mapping[str, str]], Awaitable[Envelope | None]],
    read: Callable[[object], tuple[tuple[T, ...], str | None]],
    params: Mapping[str, str],
    max_items: int | None,
    page_size: int,
    clock: Callable[[], float],
) -> AsyncIterator[T]:
    """Yield the records of a list page by page with the cursor.

    Stops on an empty page or once ``max_items`` records were yielded, without
    fetching a page it does not need.

    Args:
        fetch: Callable[[Mapping[str, str]], Awaitable[Envelope | None]] - GETs
            the list with the given parameters.
        read: Callable[[object], tuple[tuple[T, ...], str | None]] - Reads the
            items and the next cursor of a message.
        params: Mapping[str, str] - Parameters of the query.
        max_items: int | None - Most records to yield; None for all.
        page_size: int - Rows per request.
        clock: Callable[[], float] - Monotonic seconds.

    Yields:
        T - The records in Crossref's order.

    Raises:
        CrossrefCursorExpiredError: If the consumer held the walk longer than
            the cursor lives.

    """
    check_walk(max_items, page_size)
    if max_items == 0:
        return
    cursor = "*"
    yielded = 0
    answered_at: float | None = None
    while True:
        if answered_at is not None and (
            clock() - answered_at > CURSOR_LIFETIME.total_seconds()
        ):
            msg = "the cursor expired: the walk was held longer than five minutes"
            raise CrossrefCursorExpiredError(msg)
        envelope = await _fetch_page(fetch, params, cursor, page_size)
        answered_at = clock()
        if envelope is None:
            return
        items, next_cursor = read(envelope.message)
        if not items:
            return
        for item in items:
            yield item
            yielded += 1
            if max_items is not None and yielded >= max_items:
                return
        if next_cursor is None:
            return
        cursor = next_cursor
