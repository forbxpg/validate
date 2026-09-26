"""The works routes over a fake Crossref and recorded answers."""

from __future__ import annotations

import httpx
import pytest
from crossref_support import FakeCrossref, fixture, listing, make_client, ok

from vld.crossref import (
    CrossrefBadRequestError,
    CrossrefQueryError,
    PartialDate,
    WorkFacet,
    WorksFilter,
    WorksQuery,
    WorksSort,
)

PRL = "/works/10.1103/physrevlett.1.1"


async def test_get_reads_a_work_by_any_form_of_its_doi() -> None:
    """The DOI is normalized into the path; the recorded work is read."""
    fake = FakeCrossref().on(
        "GET",
        PRL,
        httpx.Response(200, json=fixture("work_journal_article")),
    )

    async with make_client(fake) as client:
        work = await client.works.get("https://doi.org/10.1103/PhysRevLett.1.1")

    assert work is not None
    assert work.doi == "10.1103/physrevlett.1.1"
    assert fake.requests[0].path == PRL


async def test_get_of_an_unknown_doi_is_none() -> None:
    """Not found is an answer."""
    async with make_client(FakeCrossref()) as client:
        assert await client.works.get("10.9999/nothing") is None


async def test_get_escapes_what_a_path_cannot_hold() -> None:
    """A DOI with ``#`` or ``?`` does not break the URL."""
    fake = FakeCrossref()

    async with make_client(fake) as client:
        _ = await client.works.get("10.1000/a#b?c")

    assert fake.requests[0].path == "/works/10.1000/a#b?c"
    assert fake.requests[0].params == {"mailto": "test@example.org"}


async def test_exists_asks_with_head() -> None:
    """No body is downloaded to learn whether a DOI exists."""
    fake = FakeCrossref().on("HEAD", PRL, httpx.Response(200))

    async with make_client(fake) as client:
        assert await client.works.exists("10.1103/PhysRevLett.1.1") is True
        assert await client.works.exists("10.9999/nothing") is False

    assert {r.method for r in fake.requests} == {"HEAD"}


async def test_agency_reads_the_registration_agency() -> None:
    """The agency of a Crossref DOI is Crossref."""
    fake = FakeCrossref().on(
        "GET",
        PRL + "/agency",
        httpx.Response(200, json=fixture("work_agency")),
    )

    async with make_client(fake) as client:
        agency = await client.works.agency("10.1103/PhysRevLett.1.1")

    assert agency is not None
    assert agency.agency is not None
    assert (agency.doi, agency.agency.id) == ("10.1103/physrevlett.1.1", "crossref")


async def test_search_sends_the_query_and_the_page_bounds() -> None:
    """A page of works with the facets Crossref counted."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(200, json=fixture("works_page_facets")),
    )
    query = WorksQuery(
        text="graphene",
        facets={WorkFacet.TYPE_NAME: 5, WorkFacet.PUBLISHED: 5},
    )

    async with make_client(fake) as client:
        page = await client.works.search(query, rows=5, offset=10)

    assert fake.requests[0].params == {
        "query": "graphene",
        "facet": "published:5,type-name:5",
        "rows": "5",
        "offset": "10",
        "mailto": "test@example.org",
    }
    assert len(page.items) == 5
    assert page.offset == 10
    assert page.total_results > 1000
    assert {facet.name for facet in page.facets} == {"type-name", "published"}


async def test_search_refuses_a_page_beyond_the_offset_window() -> None:
    """Deep pages need iterate()."""
    async with make_client(FakeCrossref()) as client:
        with pytest.raises(CrossrefQueryError, match="iterate"):
            _ = await client.works.search(rows=100, offset=9950)


async def test_iterate_walks_the_recorded_cursor_pages() -> None:
    """Two real cursor pages, then an empty one."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(200, json=fixture("works_cursor_first")),
        httpx.Response(200, json=fixture("works_cursor_second")),
        listing([]),
    )
    query = WorksQuery(filter=WorksFilter(prefix="10.1103"))

    async with make_client(fake) as client:
        dois = [
            work.doi
            async for work in client.works.iterate(query, max_items=None, page_size=3)
        ]

    assert len(dois) == 6
    assert len(set(dois)) == 6
    assert all(doi.startswith("10.1103/") for doi in dois)
    assert fake.requests[0].params["cursor"] == "*"


async def test_sample_asks_for_random_works() -> None:
    """sample=<size>, without rows or offset."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(200, json=fixture("works_sample")),
    )

    async with make_client(fake) as client:
        works = await client.works.sample(size=3)

    assert len(works) == 3
    assert fake.requests[0].params == {"sample": "3", "mailto": "test@example.org"}


@pytest.mark.parametrize(
    ("query", "size"),
    [
        (WorksQuery(), 0),
        (WorksQuery(), 101),
        (WorksQuery(sort=WorksSort.PUBLISHED), 3),
        (WorksQuery(facets={WorkFacet.ISSN: 5}), 3),
    ],
    ids=["zero", "too-many", "sorted", "faceted"],
)
async def test_sample_refuses_what_a_random_sample_cannot_do(
    query: WorksQuery,
    size: int,
) -> None:
    """Sizes outside 1..100, sorting and facets are refused."""
    async with make_client(FakeCrossref()) as client:
        with pytest.raises(CrossrefQueryError):
            _ = await client.works.sample(query, size=size)


async def test_a_refused_filter_carries_the_complaint_of_crossref() -> None:
    """The recorded validation failure reaches the caller."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        httpx.Response(400, json=fixture("works_validation_failure")),
    )

    async with make_client(fake) as client:
        with pytest.raises(CrossrefBadRequestError) as caught:
            _ = await client.works.search()

    assert caught.value.problems[0].type == "filter-not-available"


async def test_a_page_keeps_the_works_that_can_be_read() -> None:
    """One work without a DOI is dropped; the others stay."""
    fake = FakeCrossref().on(
        "GET",
        "/works",
        listing(
            [{"DOI": "10.1000/a"}, {"title": ["no doi"]}, {"DOI": "10.1000/b"}],
            total=3,
        ),
    )

    async with make_client(fake) as client:
        page = await client.works.search()

    assert [work.doi for work in page.items] == ["10.1000/a", "10.1000/b"]
    assert page.total_results == 3


async def test_a_work_without_a_doi_reads_as_none() -> None:
    """Get follows the rule of a page."""
    fake = FakeCrossref().on("GET", "/works/10.1000/a", ok({"title": ["no doi"]}))

    async with make_client(fake) as client:
        assert await client.works.get("10.1000/a") is None


def test_partial_date_is_public() -> None:
    """PartialDate is importable from the package root for filters."""
    assert PartialDate(2020).precision() == "year"
