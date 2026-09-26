"""The ``/works`` routes: a work by DOI, its agency, existence and the list."""

from __future__ import annotations

from typing import TYPE_CHECKING, final
from urllib.parse import quote

from vld.crossref.ids import normalize_doi
from vld.crossref.models import parse_item

from ._list import ALL_WORKS, WorkList, parse_work
from .model import WorkAgency

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from vld.crossref.pagination import Page
    from vld.crossref.transport import Transport

    from .model import Work
    from .query import WorksQuery


def _path(doi: str, suffix: str = "") -> str:
    return "/works/" + quote(normalize_doi(doi), safe="/") + suffix


@final
class WorksResource:
    """Works: ``client.works``."""

    def __init__(self, transport: Transport) -> None:
        self._transport: Transport = transport
        self._list: WorkList = WorkList(transport, "/works")

    async def get(self, doi: str) -> Work | None:
        """A work by DOI.

        Args:
            doi: str - The DOI in any common form.

        Returns:
            Work | None - The work, or None when Crossref has no such DOI.

        """
        envelope = await self._transport.get_json(_path(doi), {})
        return None if envelope is None else parse_work(envelope.message)

    async def exists(self, doi: str) -> bool:
        """Whether Crossref has the DOI, without downloading the work.

        Args:
            doi: str - The DOI in any common form.

        Returns:
            bool - True if the DOI is registered with Crossref.

        """
        return await self._transport.head(_path(doi))

    async def agency(self, doi: str) -> WorkAgency | None:
        """The agency the DOI is registered with.

        Args:
            doi: str - The DOI in any common form.

        Returns:
            WorkAgency | None - The agency, or None when the DOI is unknown.

        """
        envelope = await self._transport.get_json(_path(doi, "/agency"), {})
        if envelope is None:
            return None
        return parse_item(WorkAgency, envelope.message, id_key="DOI")

    async def search(
        self,
        query: WorksQuery = ALL_WORKS,
        *,
        rows: int = 20,
        offset: int = 0,
    ) -> Page[Work]:
        """One page of works, for a screen with page numbers.

        Args:
            query: WorksQuery - What to look for.
            rows: int - Rows of the page, 1..1000.
            offset: int - Works to skip; the page must end within 10,000.

        Returns:
            Page[Work] - The page.

        """
        return await self._list.search(query, rows=rows, offset=offset)

    def iterate(
        self,
        query: WorksQuery = ALL_WORKS,
        *,
        max_items: int | None,
        page_size: int = 1000,
    ) -> AsyncIterator[Work]:
        """Walk the works with the cursor, for tasks of any size.

        Args:
            query: WorksQuery - What to look for.
            max_items: int | None - Most works to yield; None walks everything.
            page_size: int - Rows per request, 1..1000.

        Returns:
            AsyncIterator[Work] - The works.

        """
        return self._list.iterate(query, max_items=max_items, page_size=page_size)

    async def sample(
        self,
        query: WorksQuery = ALL_WORKS,
        *,
        size: int,
    ) -> tuple[Work, ...]:
        """Random works matching the query.

        Args:
            query: WorksQuery - What to sample from; no sort, order or facets.
            size: int - How many, 1..100.

        Returns:
            tuple[Work, ...] - The works.

        """
        return await self._list.sample(query, size=size)
