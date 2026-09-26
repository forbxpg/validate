"""A page of a list: items, the count of all matches and the facets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from vld.crossref.errors import CrossrefQueryError, CrossrefSchemaError

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_ROWS = 1000
"""Largest page Crossref serves."""

MAX_OFFSET_WINDOW = 10_000
"""How deep ``offset`` reaches; deeper lists need the cursor."""


@dataclass(frozen=True, slots=True)
class FacetValue:
    """One value of a facet and how many matches have it.

    Attributes:
        value: str - The value.
        count: int - Matches with it (Crossref counts approximately).

    """

    value: str
    count: int


@dataclass(frozen=True, slots=True)
class Facet:
    """Counts of the values of one field among all matches.

    Attributes:
        name: str - Facet name, such as ``type-name``.
        value_count: int - How many distinct values the field has.
        values: tuple[FacetValue, ...] - The values, most frequent first.

    """

    name: str
    value_count: int
    values: tuple[FacetValue, ...]


@dataclass(frozen=True, slots=True)
class Page[T]:
    """One page of a list.

    Attributes:
        items: tuple[T, ...] - Records of the page.
        total_results: int - Matches in the whole list, as Crossref counts them.
        items_per_page: int - Rows asked for.
        offset: int - Records skipped before this page.
        facets: tuple[Facet, ...] - Facets, when asked for.

    """

    items: tuple[T, ...]
    total_results: int
    items_per_page: int
    offset: int
    facets: tuple[Facet, ...] = ()


def check_page(rows: int, offset: int) -> None:
    """Refuse page bounds Crossref would refuse.

    Args:
        rows: int - Rows asked for.
        offset: int - Records to skip.

    Raises:
        CrossrefQueryError: If ``rows`` is outside 1..1000, ``offset`` is
            negative, or the page ends beyond the first 10,000 records.

    """
    if not 1 <= rows <= MAX_ROWS:
        msg = f"rows must be within 1..{MAX_ROWS}, got {rows}"
        raise CrossrefQueryError(msg)
    if offset < 0:
        msg = f"offset must not be negative, got {offset}"
        raise CrossrefQueryError(msg)
    if offset + rows > MAX_OFFSET_WINDOW:
        msg = (
            f"offset + rows must not exceed {MAX_OFFSET_WINDOW}, got {offset + rows}; "
            "walk deeper lists with iterate()"
        )
        raise CrossrefQueryError(msg)


def _fields(message: object, route: str) -> Mapping[str, object]:
    if not isinstance(message, Mapping):
        raise CrossrefSchemaError(route=route, detail="list message is not an object")
    return cast("Mapping[str, object]", message)


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def read_items[T](
    message: object,
    parse: Callable[[object], T | None],
    *,
    route: str,
) -> tuple[tuple[T, ...], str | None]:
    """Read the items and the next cursor of a list message.

    Args:
        message: object - The ``message`` of a list answer.
        parse: Callable[[object], T | None] - Reads one item; None drops it.
        route: str - Path of the request, for the error.

    Returns:
        tuple[tuple[T, ...], str | None] - The items and ``next-cursor``.

    Raises:
        CrossrefSchemaError: If the message or its ``items`` has the wrong shape.

    """
    fields = _fields(message, route)
    raw_items = fields.get("items")
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, str):
        raise CrossrefSchemaError(route=route, detail="items is not a list")
    items = tuple(
        item for item in (parse(raw) for raw in raw_items) if item is not None
    )
    cursor = fields.get("next-cursor")
    return items, cursor if isinstance(cursor, str) else None


def parse_facets(raw: object) -> tuple[Facet, ...]:
    """Read ``{name: {"value-count": n, "values": {value: count}}}``.

    Args:
        raw: object - The ``facets`` of a list message.

    Returns:
        tuple[Facet, ...] - Facets by name, values most frequent first.

    """
    if not isinstance(raw, Mapping):
        return ()
    facets: list[Facet] = []
    for name, body in sorted(cast("Mapping[str, object]", raw).items()):
        if not isinstance(body, Mapping):
            continue
        fields = cast("Mapping[str, object]", body)
        values_raw = fields.get("values")
        values: Mapping[str, object] = (
            cast("Mapping[str, object]", values_raw)
            if isinstance(values_raw, Mapping)
            else {}
        )
        ordered = sorted(
            (FacetValue(str(value), _int(count)) for value, count in values.items()),
            key=lambda item: (-item.count, item.value),
        )
        facets.append(Facet(name, _int(fields.get("value-count")), tuple(ordered)))
    return tuple(facets)


def page_from_message[T](
    message: object,
    parse: Callable[[object], T | None],
    *,
    route: str,
    offset: int,
) -> Page[T]:
    """Build a page from a list message.

    Args:
        message: object - The ``message`` of a list answer.
        parse: Callable[[object], T | None] - Reads one item; None drops it.
        route: str - Path of the request, for the error.
        offset: int - Records skipped before the page.

    Returns:
        Page[T] - The page.

    """
    items, _ = read_items(message, parse, route=route)
    fields = _fields(message, route)
    return Page(
        items=items,
        total_results=_int(fields.get("total-results")),
        items_per_page=_int(fields.get("items-per-page")),
        offset=offset,
        facets=parse_facets(fields.get("facets")),
    )
