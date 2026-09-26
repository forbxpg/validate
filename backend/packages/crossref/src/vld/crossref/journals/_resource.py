"""The ``/journals`` routes: a journal, existence, search, walk and its works."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, final

from vld.crossref.ids import normalize_issn
from vld.crossref.models import parse_item
from vld.crossref.pagination import check_page, page_from_message, read_items, walk
from vld.crossref.works import WorkList

from ._model import Journal
from ._query import JournalsQuery

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from vld.crossref.pagination import Page
    from vld.crossref.transport import Transport

ALL_JOURNALS = JournalsQuery()
"""The empty query: every journal."""

_ROUTE = "/journals"


def parse_journal(raw: object) -> Journal | None:
    """Read one journal; a journal without a valid ISSN is dropped with a warning.

    Args:
        raw: object - The journal as Crossref sent it.

    Returns:
        Journal | None - The journal, or None.

    """
    return parse_item(Journal, raw, id_key="ISSN")


@final
class JournalsResource:
    """Journals: ``client.journals``."""

    def __init__(self, transport: Transport) -> None:
        self._transport: Transport = transport

    async def get(self, issn: str) -> Journal | None:
        """A journal by ISSN.

        Args:
            issn: str - The ISSN in any common form.

        Returns:
            Journal | None - The journal, or None when Crossref has no such ISSN.

        """
        envelope = await self._transport.get_json(
            f"{_ROUTE}/{normalize_issn(issn)}",
            {},
        )
        return None if envelope is None else parse_journal(envelope.message)

    async def exists(self, issn: str) -> bool:
        """Whether Crossref knows the ISSN, without downloading the journal.

        Args:
            issn: str - The ISSN in any common form.

        Returns:
            bool - True if Crossref has the journal.

        """
        return await self._transport.head(f"{_ROUTE}/{normalize_issn(issn)}")

    async def search(
        self,
        query: JournalsQuery = ALL_JOURNALS,
        *,
        rows: int = 20,
        offset: int = 0,
    ) -> Page[Journal]:
        """One page of journals, for a screen with page numbers.

        Args:
            query: JournalsQuery - What to look for.
            rows: int - Rows of the page, 1..1000.
            offset: int - Journals to skip; the page must end within 10,000.

        Returns:
            Page[Journal] - The page.

        """
        check_page(rows, offset)
        params = {**query.params(), "rows": str(rows), "offset": str(offset)}
        envelope = await self._transport.get_json(_ROUTE, params)
        message: object = {"items": []} if envelope is None else envelope.message
        return page_from_message(message, parse_journal, route=_ROUTE, offset=offset)

    def iterate(
        self,
        query: JournalsQuery = ALL_JOURNALS,
        *,
        max_items: int | None,
        page_size: int = 1000,
    ) -> AsyncIterator[Journal]:
        """Walk the journals with the cursor; ``max_items=None`` walks them all.

        Args:
            query: JournalsQuery - What to look for.
            max_items: int | None - Most journals to yield; None walks everything.
            page_size: int - Rows per request, 1..1000.

        Returns:
            AsyncIterator[Journal] - The journals.

        """
        return walk(
            fetch=partial(self._transport.get_json, _ROUTE),
            read=partial(read_items, parse=parse_journal, route=_ROUTE),
            params=query.params(),
            max_items=max_items,
            page_size=page_size,
            clock=self._transport.clock,
        )

    def works(self, issn: str) -> WorkList:
        """The works of one journal, with the full works query.

        Args:
            issn: str - The ISSN in any common form.

        Returns:
            WorkList - Search, walk and sample on ``/journals/{issn}/works``.

        """
        return WorkList(self._transport, f"{_ROUTE}/{normalize_issn(issn)}/works")
