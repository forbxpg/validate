"""План ленты по SQL, снятому С настоящего вызова репозитория — на все пять."""

from __future__ import annotations

from contextlib import ExitStack
from typing import TYPE_CHECKING, cast

from sqlalchemy import text

from .sql_capture import capture_selects

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable, Sequence

    from fastapi_pagination.cursor import CursorPage
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from vld.core.pagination import Page

PAGES = 2


async def explain_feed_pages(  # ruff: ignore[too-many-arguments] -- engine, session and call are indivisible,
    engine: AsyncEngine,
    session: AsyncSession,
    table: str,
    page: Callable[[str | None], Awaitable[Page[uuid.UUID]]],
    *,
    knobs: Sequence[str],
    companions: Sequence[str] = (),
) -> list[str]:
    """Go through the feed on two pages and return the plan of each.

    Args:
        engine: AsyncEngine - The engine on which ``before_cursor_execute`` is listened.
        session: AsyncSession - The session of the test.
        table: str - The qualified name of the feed table.
        page: Callable - The call of the repository.
        knobs: Sequence[str] - The names of the planner parameters, turned off during
            ``EXPLAIN``.
        companions: Sequence[str] - The qualified names of the companion tables, which
            the page reads along.

    Returns:
        list[str] - The plans of the pages in order.

    """
    with ExitStack() as stack:
        captured = stack.enter_context(capture_selects(engine, table))
        alongside = {
            companion: stack.enter_context(capture_selects(engine, companion))
            for companion in companions
        }
        first = await page(None)
        cursor = cast("CursorPage[uuid.UUID]", first).next_page
        assert cursor is not None, (
            "the first page did not produce a cursor: there are too few rows"
        )
        _ = await page(cursor)

    assert len(captured) == PAGES, (
        f"it took more than two requests to go through two pages: {captured}"
    )
    for companion, statements in alongside.items():
        assert len(statements) == PAGES, (
            f"{companion}: it took more than two requests to go through two pages — this is either reading "
            f"a row instead of a batch, or a missing read: {statements}"
        )

    connection = await session.connection()
    for knob in knobs:
        _ = await connection.execute(text(f"SET LOCAL {knob} = off"))
    plans: list[str] = []
    for statement, parameters in captured:
        rows = await connection.exec_driver_sql("EXPLAIN " + statement, parameters)  # pyright: ignore[reportArgumentType]
        plans.append("\n".join(cast("Sequence[str]", [row[0] for row in rows])))
    return plans
