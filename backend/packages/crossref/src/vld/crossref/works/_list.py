"""Any works route that lists works: ``/works`` and ``/journals/{issn}/works``."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, final

from vld.crossref.errors import CrossrefQueryError
from vld.crossref.models import parse_item
from vld.crossref.pagination import check_page, page_from_message, read_items, walk

from .model import Work
from .query import WorksQuery

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from vld.crossref.pagination import Page
    from vld.crossref.transport import Transport

ALL_WORKS = WorksQuery()
"""The empty query: every work of the route."""

SAMPLE_MAX = 100
"""Largest random sample Crossref serves."""


def parse_work(raw: object) -> Work | None:
    """Read one work; a work without a valid DOI is dropped with a warning.

    Args:
        raw: object - The work as Crossref sent it.

    Returns:
        Work | None - The work, or None.

    """
    return parse_item(Work, raw, id_key="DOI")


@final
class WorkList:
    """Search, walk and sample the works of one route."""

    def __init__(self, transport: Transport, route: str) -> None:
        self._transport: Transport = transport
        self._route: str = route

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
        check_page(rows, offset)
        params = {**query.params(), "rows": str(rows), "offset": str(offset)}
        envelope = await self._transport.get_json(self._route, params)
        message: object = {"items": []} if envelope is None else envelope.message
        return page_from_message(message, parse_work, route=self._route, offset=offset)

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
        return walk(
            fetch=partial(self._transport.get_json, self._route),
            read=partial(read_items, parse=parse_work, route=self._route),
            params=query.params(),
            max_items=max_items,
            page_size=page_size,
            clock=self._transport.clock,
        )

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

        Raises:
            CrossrefQueryError: If the size is out of range or the query sorts or
                asks for facets.

        """
        if not 1 <= size <= SAMPLE_MAX:
            msg = f"sample size must be within 1..{SAMPLE_MAX}, got {size}"
            raise CrossrefQueryError(msg)
        if query.sort is not None or query.facets:
            msg = "a sample has no order and no facets"
            raise CrossrefQueryError(msg)
        params = {**query.params(), "sample": str(size)}
        envelope = await self._transport.get_json(self._route, params)
        if envelope is None:
            return ()
        items, _ = read_items(envelope.message, parse_work, route=self._route)
        return items
