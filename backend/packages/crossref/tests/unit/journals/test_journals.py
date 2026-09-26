"""The journals routes and the Journal model over recorded answers."""

from __future__ import annotations

from typing import cast

import httpx
import pytest
from crossref_support import FakeCrossref, fixture, listing, make_client
from structlog.testing import capture_logs

from vld.crossref import (
    CrossrefBadRequestError,
    CrossrefQueryError,
    Journal,
    JournalsQuery,
    PartialDate,
    WorksFilter,
    WorksQuery,
    WorksSort,
)
from vld.crossref.journals._resource import parse_journal

PRL = "/journals/0031-9007"


def _journal(name: str) -> Journal:
    body = cast("dict[str, object]", fixture(name))
    journal = parse_journal(body["message"])
    assert journal is not None
    return journal


def test_a_journal_is_read_whole_without_degradation() -> None:
    """ISSNs by kind, counts, years, coverage and flags."""
    with capture_logs() as logs:
        journal = _journal("journal_prl")

    assert logs == []
    assert journal.title == "Physical Review Letters"
    assert (journal.issn_print, journal.issn_electronic) == ("0031-9007", "1079-7114")
    assert journal.issns == ("0031-9007", "1079-7114")
    assert journal.total_dois is not None
    assert journal.total_dois > 100_000
    assert journal.dois_by_year[2008] > 0
    assert "affiliation-ror-ids-backfile" in journal.coverage
    assert set(journal.coverage_type) == {"all", "current", "backfile"}
    assert all(
        "last-status-check-time" not in body for body in journal.coverage_type.values()
    )
    assert journal.flags["deposits"] is True
    assert journal.last_status_check is not None
    assert journal.last_status_check.tzinfo is not None


def test_a_malformed_journal_degrades_and_keeps_its_valid_issn() -> None:
    """A bad ISSN is dropped, one issn-type object is read, subjects of both shapes."""
    with capture_logs() as logs:
        journal = _journal("journal_malformed_handmade")

    assert journal.issn == ("1079-7114",)
    assert journal.issn_electronic == "1079-7114"
    assert journal.counts is None
    assert journal.subjects == ("Physics", "General Physics")
    assert {entry["field"] for entry in logs} == {"issn", "counts"}


def test_a_journal_without_a_valid_issn_is_not_read() -> None:
    """No ISSN, no journal."""
    with capture_logs() as logs:
        journal = parse_journal({"title": "Nameless", "ISSN": ["0000-0001"]})

    assert journal is None
    assert logs[-1]["event"] == "crossref_item_dropped"


async def test_get_normalizes_the_issn_into_the_path() -> None:
    """Any common form of an ISSN reaches the same path."""
    fake = FakeCrossref().on(
        "GET",
        PRL,
        httpx.Response(200, json=fixture("journal_prl")),
    )

    async with make_client(fake) as client:
        journal = await client.journals.get("0031 9007")

    assert journal is not None
    assert fake.requests[0].path == PRL


async def test_an_issn_with_a_wrong_check_digit_is_refused_before_a_request() -> None:
    """A typo never reaches Crossref."""
    fake = FakeCrossref()

    async with make_client(fake) as client:
        with pytest.raises(CrossrefQueryError):
            _ = await client.journals.get("0031-9008")

    assert fake.requests == []


async def test_get_of_an_unknown_journal_is_none_and_exists_uses_head() -> None:
    """Not found is an answer; existence downloads nothing."""
    fake = FakeCrossref().on("HEAD", PRL, httpx.Response(200))

    async with make_client(fake) as client:
        assert await client.journals.get("1234-5679") is None
        assert await client.journals.exists("0031-9007") is True
        assert await client.journals.exists("1234-5679") is False


async def test_search_sends_only_what_the_route_accepts() -> None:
    """query, rows and offset."""
    fake = FakeCrossref().on(
        "GET",
        "/journals",
        httpx.Response(200, json=fixture("journals_page")),
    )

    async with make_client(fake) as client:
        page = await client.journals.search(
            JournalsQuery(text="physical review"),
            rows=5,
        )

    assert fake.requests[0].params == {
        "query": "physical review",
        "rows": "5",
        "offset": "0",
        "mailto": "test@example.org",
    }
    assert len(page.items) == 5


async def test_iterate_walks_every_journal_with_the_cursor() -> None:
    """max_items=None walks until an empty page."""
    fake = FakeCrossref().on(
        "GET",
        "/journals",
        httpx.Response(200, json=fixture("journals_cursor_first")),
        httpx.Response(200, json=fixture("journals_cursor_second")),
        listing([]),
    )

    async with make_client(fake) as client:
        journals = [
            journal
            async for journal in client.journals.iterate(max_items=None, page_size=3)
        ]

    assert len(journals) == 6
    assert len({journal.issns for journal in journals}) == 6
    assert [r.params["cursor"] for r in fake.requests][:1] == ["*"]


async def test_iterate_stops_at_max_items() -> None:
    """No page more than needed."""
    fake = FakeCrossref().on(
        "GET",
        "/journals",
        httpx.Response(200, json=fixture("journals_cursor_first")),
        httpx.Response(200, json=fixture("journals_cursor_second")),
    )

    async with make_client(fake) as client:
        journals = [
            journal
            async for journal in client.journals.iterate(max_items=2, page_size=3)
        ]

    assert len(journals) == 2
    assert len(fake.requests) == 1


async def test_the_works_of_a_journal_take_the_full_works_query() -> None:
    """The same query, pages and walk as /works, on the route of the journal."""
    fake = FakeCrossref().on(
        "GET",
        PRL + "/works",
        httpx.Response(200, json=fixture("journal_works_page")),
    )
    query = WorksQuery(
        sort=WorksSort.PUBLISHED,
        filter=WorksFilter(from_pub_date=PartialDate(2024)),
    )

    async with make_client(fake) as client:
        page = await client.journals.works("00319007").search(query, rows=3)

    assert fake.requests[0].path == PRL + "/works"
    assert fake.requests[0].params["filter"] == "from-pub-date:2024"
    assert len(page.items) == 3


async def test_the_route_refuses_filters() -> None:
    """The recorded refusal of Crossref reaches the caller as it is."""
    fake = FakeCrossref().on(
        "GET",
        "/journals",
        httpx.Response(400, json=fixture("journals_filter_refused")),
    )

    async with make_client(fake) as client:
        with pytest.raises(CrossrefBadRequestError) as caught:
            _ = await client.journals.search()

    assert caught.value.problems[0].type == "parameter-not-allowed"


def test_the_journals_query_renders_text_only() -> None:
    """Text is the only parameter of the route."""
    assert JournalsQuery(text="  nature ").params() == {"query": "nature"}
    assert JournalsQuery().params() == {}
    with pytest.raises(CrossrefQueryError):
        _ = JournalsQuery.model_validate({"filter": "x"})


def test_the_print_issn_comes_first_whatever_the_order_sent() -> None:
    """Issns puts the print ISSN first even when Crossref lists it second."""
    journal = parse_journal(
        {
            "ISSN": ["1079-7114", "0031-9007"],
            "issn-type": [
                {"type": "electronic", "value": "1079-7114"},
                {"type": "print", "value": "0031-9007"},
            ],
        },
    )

    assert journal is not None
    assert journal.issns == ("0031-9007", "1079-7114")


async def test_search_refuses_a_page_beyond_the_offset_window() -> None:
    """Deep pages of journals need iterate()."""
    async with make_client(FakeCrossref()) as client:
        with pytest.raises(CrossrefQueryError, match="iterate"):
            _ = await client.journals.search(rows=100, offset=9950)
