"""Capture SQL, that went to the database, — by a listener, not by rewriting the query."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import event

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator

    from sqlalchemy.ext.asyncio import AsyncEngine


@contextmanager
def capture_selects(
    engine: AsyncEngine,
    table: str,
) -> Generator[list[tuple[str, object]]]:
    """Collect SELECTs by table, while the block is open.

    Args:
        engine: AsyncEngine - The engine on which ``before_cursor_execute`` is listened.
        table: str - The qualified name of the table.

    Yields:
        list[tuple[str, object]] - The captured pairs «statement, parameters».

    """
    captured: list[tuple[str, object]] = []

    def _capture(
        _conn: object,
        _cursor: object,
        statement: str,
        parameters: object,
        _context: object,
        _executemany: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
    ) -> None:
        if table in statement and statement.lstrip().startswith("SELECT"):
            captured.append((statement, parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", _capture)
    try:
        yield captured
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture)


async def count_selects[T](
    engine: AsyncEngine,
    table: str,
    call: Callable[[], Awaitable[T]],
) -> tuple[T, list[str]]:
    """Call the repository and count how many requests it cost.

    Args:
        engine: AsyncEngine - The engine on which the event is listened.
        table: str - The qualified name of the table.
        call: Callable - The call of the repository without arguments.

    Returns:
        tuple[T, list[str]] - What the call returned and the texts of the SELECTs that went.

    """
    with capture_selects(engine, table) as captured:
        result = await call()
    return result, [statement for statement, _ in captured]
