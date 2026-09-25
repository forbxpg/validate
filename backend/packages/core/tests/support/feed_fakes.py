"""Страница ленты, собранная в памяти, — общая заглушка на все ленты проекта."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, cast

from fastapi_pagination import create_page

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from fastapi_pagination.bases import AbstractParams, CursorRawParams

    from vld.core.pagination import Page, PageParams, Projection


class _FeedRow(Protocol):
    """The little that the page of the feed needs to know about the row.

    Attributes:
        id: uuid.UUID - The identifier of the row, it is also the cursor.

    """

    @property
    def id(self) -> uuid.UUID: ...


async def feed_page[RowT: _FeedRow, ProjectedT](
    rows: Sequence[RowT],
    keep: Callable[[RowT], bool],
    params: PageParams,
    project: Projection[RowT, ProjectedT],
    *,
    newest_first: bool = True,
) -> Page[ProjectedT]:
    """Collect the page of the feed in memory — common for all three fakes.

    Args:
        rows: Sequence - All rows of the fake, in the order of insertion.
        keep: Callable - Who to let on the page.
        params: PageParams - The parameters of the page, cursor inside.
        project: Projection - The projection of the caller.
        newest_first: bool - Fresh first (feeds) or old first (discussion under the post).

    Returns:
        Page - The page with the applied projection and cursor forward.

    """
    raw = cast("CursorRawParams", params.to_raw_params())
    ordered = reversed(rows) if newest_first else rows
    feed = [row for row in ordered if keep(row)]
    start = 0
    if raw.cursor is not None:
        start = 1 + next(
            index for index, row in enumerate(feed) if str(row.id) == raw.cursor
        )
    window = feed[start : start + raw.size]
    projected = project(window)
    items = projected if isinstance(projected, Sequence) else await projected
    return cast(  # pyright: ignore[reportInvalidCast]
        "Page[ProjectedT]",
        create_page(
            items,
            total=len(feed),
            params=cast("AbstractParams", params),
            next_=str(window[-1].id) if start + len(window) < len(feed) else None,
        ),
    )
