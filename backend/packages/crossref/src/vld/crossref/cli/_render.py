"""What a person sees in a terminal and what a script gets otherwise."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import TextIO

    from pydantic import BaseModel

    from vld.crossref import Facet, Journal, Page, Work
    from vld.crossref.works.model import Contributor

_AUTHORS_SHOWN = 10
_MISSING = "—"


def dump(model: BaseModel) -> object:
    """Turn a record into JSON-ready data with Crossref's field names.

    Args:
        model: BaseModel - A work, a journal or an agency.

    Returns:
        object - JSON-ready data.

    """
    return model.model_dump(mode="json", by_alias=True)


def page_document[T: BaseModel](page: Page[T]) -> dict[str, object]:
    """Describe a search page as one JSON document.

    Args:
        page: Page[T] - The page.

    Returns:
        dict[str, object] - Totals, position, facets and items.

    """
    return {
        "total_results": page.total_results,
        "offset": page.offset,
        "rows": page.items_per_page,
        "facets": [
            {
                "name": facet.name,
                "value_count": facet.value_count,
                "values": [
                    {"value": value.value, "count": value.count}
                    for value in facet.values
                ],
            }
            for facet in page.facets
        ],
        "items": [dump(item) for item in page.items],
    }


def write_document(stream: TextIO, document: object) -> None:
    """Print one JSON document.

    Args:
        stream: TextIO - Where to print.
        document: object - JSON-ready data.

    """
    _ = stream.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def write_line(stream: TextIO, record: object) -> None:
    """Print one record as a JSON line and flush it.

    Args:
        stream: TextIO - Where to print.
        record: object - JSON-ready data.

    """
    _ = stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    stream.flush()


def _person(contributor: Contributor) -> str:
    name = " ".join(part for part in (contributor.given, contributor.family) if part)
    return name or contributor.name or _MISSING


def work_panel(work: Work) -> Panel:
    """Show one work as a card.

    Args:
        work: Work - The work.

    Returns:
        Panel - The card.

    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column()
    doi_link = Text(work.doi, style=f"link https://doi.org/{work.doi}")
    grid.add_row("DOI", doi_link)
    grid.add_row("Type", str(work.type) if work.type else _MISSING)
    journal = work.journal_title or _MISSING
    issns = ", ".join(
        f"{kind} {value}"
        for kind, value in (
            ("print", work.issn_print),
            ("electronic", work.issn_electronic),
        )
        if value
    )
    grid.add_row("Journal", f"{journal} ({issns})" if issns else journal)
    grid.add_row("Published", str(work.publication_date or _MISSING))
    authors = [
        _person(author) + (f" · ORCID {author.orcid}" if author.orcid else "")
        for author in work.author[:_AUTHORS_SHOWN]
    ]
    hidden = len(work.author) - _AUTHORS_SHOWN
    if hidden > 0:
        authors.append(f"and {hidden} more")
    grid.add_row("Authors", "\n".join(authors) or _MISSING)
    grid.add_row("Publisher", work.publisher or _MISSING)
    grid.add_row("References", str(work.reference_count or 0))
    grid.add_row("Cited by", str(work.is_referenced_by_count or 0))
    licenses = [item.url for item in work.license if item.url]
    grid.add_row("Licenses", "\n".join(licenses) or _MISSING)
    full_text = next((item.url for item in work.link if item.url), None)
    grid.add_row("Full text", full_text or _MISSING)
    return Panel(grid, title=work.main_title or work.doi, title_align="left")


def works_table(works: Iterable[Work]) -> Table:
    """Show works as rows.

    Args:
        works: Iterable[Work] - The works.

    Returns:
        Table - DOI, year, first author, title, journal.

    """
    table = Table(show_lines=False, expand=True)
    table.add_column("DOI", no_wrap=True, style="cyan")
    table.add_column("Year", no_wrap=True)
    table.add_column("First author", max_width=24, overflow="ellipsis", no_wrap=True)
    table.add_column("Title", overflow="ellipsis", no_wrap=True, ratio=3)
    table.add_column("Journal", overflow="ellipsis", no_wrap=True, ratio=1)
    for work in works:
        table.add_row(
            work.doi,
            str(work.year or _MISSING),
            _person(work.author[0]) if work.author else _MISSING,
            work.main_title or _MISSING,
            work.journal_title or _MISSING,
        )
    return table


def journal_panel(journal: Journal) -> Panel:
    """Show one journal as a card.

    Args:
        journal: Journal - The journal.

    Returns:
        Panel - The card.

    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column()
    grid.add_row("Publisher", journal.publisher or _MISSING)
    grid.add_row("ISSN print", journal.issn_print or _MISSING)
    grid.add_row("ISSN electronic", journal.issn_electronic or _MISSING)
    grid.add_row(
        "DOIs",
        str(journal.total_dois if journal.total_dois is not None else _MISSING),
    )
    grid.add_row("Subjects", ", ".join(journal.subjects) or _MISSING)
    return Panel(
        grid,
        title=journal.title or ", ".join(journal.issns),
        title_align="left",
    )


def journals_table(journals: Iterable[Journal]) -> Table:
    """Show journals as rows.

    Args:
        journals: Iterable[Journal] - The journals.

    Returns:
        Table - Title, ISSNs, publisher, DOIs.

    """
    table = Table(expand=True)
    table.add_column("Title", overflow="ellipsis", no_wrap=True, ratio=3)
    table.add_column("ISSN", no_wrap=True, style="cyan")
    table.add_column("Publisher", overflow="ellipsis", no_wrap=True, ratio=2)
    table.add_column("DOIs", justify="right", no_wrap=True)
    for journal in journals:
        table.add_row(
            journal.title or _MISSING,
            ", ".join(journal.issns) or _MISSING,
            journal.publisher or _MISSING,
            str(journal.total_dois if journal.total_dois is not None else _MISSING),
        )
    return table


def facet_table(facet: Facet) -> Table:
    """Show one facet with its counts.

    Args:
        facet: Facet - The facet.

    Returns:
        Table - Value and count.

    """
    table = Table(title=f"{facet.name} ({facet.value_count} values)")
    table.add_column("Value")
    table.add_column("Count", justify="right")
    for value in facet.values:
        table.add_row(value.value, f"{value.count:,}".replace(",", " "))
    return table


def summary(*, shown: int, total: int | None, offset: int, pool: str | None) -> str:
    """Say how much of the result is on the screen and in which pool.

    Args:
        shown: int - Records shown.
        total: int | None - Records matching, when Crossref said.
        offset: int - Position of the first record.
        pool: str | None - The pool of the last answer.

    Returns:
        str - Such as `20 of 1 234 567 · from 0 · pool: polite`.

    """
    parts = [
        f"{shown} of {total:,}".replace(",", " ") if total is not None else f"{shown}",
    ]
    if offset:
        parts.append(f"from {offset}")
    parts.append(f"pool: {pool or 'unknown'}")
    return " · ".join(parts)
