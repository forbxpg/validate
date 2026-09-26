"""The real Crossref: journals by ISSN, the cursor, refused filters (crossref_live)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vld.crossref import CrossrefBadRequestError, JournalsQuery

if TYPE_CHECKING:
    from vld.crossref import CrossrefClient

pytestmark = pytest.mark.crossref_live


async def test_a_journal_is_read_with_both_issns(live: CrossrefClient) -> None:
    """Physical Review Letters, print and electronic."""
    journal = await live.journals.get("0031-9007")

    assert journal is not None
    assert (journal.issn_print, journal.issn_electronic) == ("0031-9007", "1079-7114")


async def test_three_cursor_pages_of_journals_are_distinct(
    live: CrossrefClient,
) -> None:
    """The journals route walks with the cursor too."""
    journals = [
        journal async for journal in live.journals.iterate(max_items=9, page_size=3)
    ]

    assert len({journal.issns for journal in journals}) == 9


async def test_the_journals_route_still_refuses_filters(live: CrossrefClient) -> None:
    """If Crossref starts accepting filters here, JournalsQuery must grow."""
    with pytest.raises(CrossrefBadRequestError):
        _ = await live._transport.get_json("/journals", {"filter": "type:x"})
    assert JournalsQuery().params() == {}
