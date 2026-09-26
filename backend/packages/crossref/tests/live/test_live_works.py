"""The real Crossref: works catalogues, identifiers, filters, cursors (crossref_live)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import pytest
from catalogue_lists import (
    LIVE_FACETS,
    LIVE_FIELD_QUERIES,
    LIVE_FILTERS,
    LIVE_SELECT,
    LIVE_SORT,
    LIVE_TYPES,
)

from vld.crossref import CrossrefBadRequestError, WorksFilter, WorksQuery

if TYPE_CHECKING:
    from vld.crossref import CrossrefClient

pytestmark = pytest.mark.crossref_live

_LISTED = re.compile(r"(?:are|one of): (.+)$")


async def _listed(live: CrossrefClient, params: dict[str, str]) -> set[str]:
    with pytest.raises(CrossrefBadRequestError) as caught:
        _ = await live._transport.get_json("/works", {"rows": "0", **params})
    match = _LISTED.search(caught.value.problems[0].message.strip())
    assert match is not None, caught.value.problems
    return {name.strip() for name in match.group(1).split(",")}


async def test_the_catalogues_are_still_what_crossref_accepts(
    live: CrossrefClient,
) -> None:
    """Filters, field queries, select, facets and sort fields have not changed."""
    assert await _listed(live, {"filter": "zzz:1"}) == set(LIVE_FILTERS)
    assert await _listed(live, {"query.zzz": "a"}) == set(LIVE_FIELD_QUERIES)
    assert await _listed(live, {"select": "zzz"}) == set(LIVE_SELECT)
    assert await _listed(live, {"facet": "zzz:5"}) == {*LIVE_FACETS, "*"}
    assert await _listed(live, {"sort": "zzz"}) == set(LIVE_SORT)


async def test_the_work_types_are_still_what_crossref_lists(
    live: CrossrefClient,
) -> None:
    """``/types`` names the same 30 types as WorkType."""
    envelope = await live._transport.get_json("/types", {"rows": "1000"})

    assert envelope is not None
    items = cast("dict[str, list[dict[str, str]]]", envelope.message)["items"]
    assert {item["id"] for item in items} == set(LIVE_TYPES)


async def test_a_known_doi_is_read_and_an_unknown_one_does_not_exist(
    live: CrossrefClient,
) -> None:
    """get, exists and agency against real records."""
    work = await live.works.get("10.1103/PhysRevLett.1.1")

    assert work is not None
    assert work.journal_title == "Physical Review Letters"
    assert await live.works.exists("10.9999/definitely-not-there") is False
    agency = await live.works.agency("10.1103/PhysRevLett.1.1")
    assert agency is not None
    assert agency.agency is not None
    assert agency.agency.id == "crossref"


async def test_repeated_values_of_one_filter_are_ored(live: CrossrefClient) -> None:
    """count(A) + count(B) == count(A or B) for two disjoint prefixes."""
    first = await live.works.search(
        WorksQuery(filter=WorksFilter(prefix="10.1103")),
        rows=1,
    )
    second = await live.works.search(
        WorksQuery(filter=WorksFilter(prefix="10.1063")),
        rows=1,
    )
    both = await live.works.search(
        WorksQuery(filter=WorksFilter(prefix=["10.1103", "10.1063"])),
        rows=1,
    )

    assert both.total_results == first.total_results + second.total_results


async def test_three_cursor_pages_of_works_are_distinct(live: CrossrefClient) -> None:
    """The cursor moves forward."""
    query = WorksQuery(filter=WorksFilter(prefix="10.1103"))

    dois = [
        work.doi async for work in live.works.iterate(query, max_items=9, page_size=3)
    ]

    assert len(set(dois)) == 9
