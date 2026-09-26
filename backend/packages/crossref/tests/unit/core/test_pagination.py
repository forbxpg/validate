"""Pages for screens and cursor walks for everything."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import httpx
import pytest
from crossref_support import FakeClock, FakeCrossref, listing, make_client

from vld.crossref import (
    CrossrefCursorExpiredError,
    CrossrefQueryError,
    Facet,
    FacetValue,
)
from vld.crossref.pagination import (
    check_page,
    page_from_message,
    parse_facets,
    read_items,
    walk,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from vld.crossref import CrossrefClient


def _id(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    value = cast("dict[str, object]", raw).get("id")
    return value if isinstance(value, str) else None


def _ids(message: object) -> tuple[tuple[str, ...], str | None]:
    return read_items(message, _id, route="/things")


def _walk(
    client: CrossrefClient,
    clock: FakeClock,
    *,
    max_items: int | None,
    page_size: int = 2,
):
    async def fetch(params: Mapping[str, str]):
        return await client._transport.get_json("/things", params)

    return walk(
        fetch=fetch,
        read=_ids,
        params={"query": "x"},
        max_items=max_items,
        page_size=page_size,
        clock=clock,
    )


@pytest.mark.parametrize(
    ("rows", "offset"),
    [(0, 0), (1001, 0), (10, -1), (1000, 9001)],
)
def test_page_bounds_crossref_would_refuse_are_refused_first(
    rows: int,
    offset: int,
) -> None:
    """Rows 1..1000, offset not negative, no page beyond the first 10,000 records."""
    with pytest.raises(CrossrefQueryError):
        check_page(rows, offset)


def test_the_last_reachable_page_is_allowed() -> None:
    """Offset + rows equal to 10,000 is still served."""
    check_page(1000, 9000)


def test_a_page_counts_all_matches_and_keeps_its_facets() -> None:
    """total-results, items-per-page and facets are read."""
    message = {
        "items": [{"id": "a"}, {"id": "b"}, {"nope": 1}],
        "total-results": 42,
        "items-per-page": 3,
        "facets": {
            "type-name": {
                "value-count": 2,
                "values": {"Book": 1, "Journal Article": 5},
            },
        },
    }

    page = page_from_message(message, _id, route="/things", offset=10)

    assert page.items == ("a", "b")
    assert (page.total_results, page.items_per_page, page.offset) == (42, 3, 10)
    assert page.facets == (
        Facet(
            "type-name",
            2,
            (FacetValue("Journal Article", 5), FacetValue("Book", 1)),
        ),
    )


def test_malformed_facets_are_skipped() -> None:
    """Facets are a courtesy; a strange one does not break the page."""
    assert parse_facets({"a": "x", "b": {"values": "y"}}) == (Facet("b", 0, ()),)
    assert parse_facets(None) == ()


async def test_a_walk_follows_the_cursor_until_an_empty_page() -> None:
    """Cursor * first, then each next-cursor."""
    clock = FakeClock()
    fake = FakeCrossref().on(
        "GET",
        "/things",
        listing([{"id": "a"}, {"id": "b"}], cursor="c1"),
        listing([{"id": "c"}], cursor="c2"),
        listing([], cursor="c3"),
    )

    async with make_client(fake, clock=clock) as client:
        found = [item async for item in _walk(client, clock, max_items=None)]

    assert found == ["a", "b", "c"]
    assert [r.params["cursor"] for r in fake.requests] == ["*", "c1", "c2"]
    assert all(
        r.params["rows"] == "2" and r.params["query"] == "x" for r in fake.requests
    )


async def test_a_walk_stops_at_max_items_without_another_request() -> None:
    """No page is fetched that is not needed."""
    clock = FakeClock()
    fake = FakeCrossref().on(
        "GET",
        "/things",
        listing([{"id": "a"}, {"id": "b"}], cursor="c1"),
        listing([{"id": "c"}], cursor="c2"),
    )

    async with make_client(fake, clock=clock) as client:
        found = [item async for item in _walk(client, clock, max_items=2)]
        nothing = [item async for item in _walk(client, clock, max_items=0)]

    assert found == ["a", "b"]
    assert nothing == []
    assert len(fake.requests) == 1


async def test_a_cursor_held_longer_than_five_minutes_expires() -> None:
    """The walk says so instead of starting over."""
    clock = FakeClock()
    fake = FakeCrossref().on(
        "GET",
        "/things",
        listing([{"id": "a"}, {"id": "b"}], cursor="c1"),
        listing([{"id": "c"}], cursor="c2"),
    )

    async with make_client(fake, clock=clock) as client:
        walker = _walk(client, clock, max_items=None)
        assert await anext(walker) == "a"
        assert await anext(walker) == "b"
        clock.now += 301
        with pytest.raises(CrossrefCursorExpiredError):
            _ = await anext(walker)


async def test_a_cursor_refused_by_crossref_expires() -> None:
    """A 400 about a later cursor means it expired."""
    clock = FakeClock()
    refusal = {
        "status": "failed",
        "message": [{"type": "cursor-not-found", "value": "c1", "message": "x"}],
    }
    fake = FakeCrossref().on(
        "GET",
        "/things",
        listing([{"id": "a"}], cursor="c1"),
        httpx.Response(400, json=refusal),
    )

    async with make_client(fake, clock=clock) as client:
        with pytest.raises(CrossrefCursorExpiredError):
            _ = [
                item async for item in _walk(client, clock, max_items=None, page_size=1)
            ]


@pytest.mark.parametrize(
    ("max_items", "page_size"),
    [(-1, 10), (None, 0), (None, 1001)],
)
async def test_walk_bounds_are_refused(max_items: int | None, page_size: int) -> None:
    """A negative max_items or a page size outside 1..1000 is a mistake."""
    clock = FakeClock()
    async with make_client(FakeCrossref(), clock=clock) as client:
        with pytest.raises(CrossrefQueryError):
            _ = [
                item
                async for item in _walk(
                    client,
                    clock,
                    max_items=max_items,
                    page_size=page_size,
                )
            ]
