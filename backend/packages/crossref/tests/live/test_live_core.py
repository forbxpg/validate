"""The real Crossref: the pool, the envelope and a cursor (marked crossref_live)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from vld.crossref import CrossrefClient

pytestmark = pytest.mark.crossref_live


async def test_a_request_is_answered_and_the_pool_is_known(
    live: CrossrefClient,
) -> None:
    """The envelope parses and the pool header is read."""
    envelope = await live._transport.get_json("/works", {"rows": "0"})

    assert envelope is not None
    assert envelope.message_type == "work-list"
    assert live.pool is not None


async def test_an_unknown_path_reads_as_none(live: CrossrefClient) -> None:
    """Crossref answers 404 for a DOI it does not know."""
    assert (
        await live._transport.get_json("/works/10.9999/definitely-not-there", {})
        is None
    )
    assert await live._transport.head("/works/10.9999/definitely-not-there") is False
