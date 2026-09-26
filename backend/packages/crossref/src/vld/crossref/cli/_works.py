"""`vld-crossref works`: a work by DOI, searches, walks, samples, the filters."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table

from vld.crossref.ids import normalize_doi

from ._options import Common, QueryInput, with_options
from ._query import build_works_query, filter_specs
from ._render import facet_table, work_panel, works_table, write_document
from ._runtime import EXIT_NOT_FOUND, Output, run

if TYPE_CHECKING:
    from vld.crossref import CrossrefClient
    from vld.crossref.works import WorkList, WorksResource

DEFAULT_WALK = 100
"""Records a walk takes without `--max` or `--all`."""

works_app = typer.Typer(
    name="works",
    help="Works: get one by DOI, search, walk, sample.",
    no_args_is_help=True,
)

Doi = Annotated[
    str,
    typer.Argument(help="DOI in any form: 10.1103/…, doi:…, https://doi.org/…"),
]


def _target(client: CrossrefClient, journal: str | None) -> WorksResource | WorkList:
    return client.works if journal is None else client.journals.works(journal)


@works_app.command("get")
@with_options()
def get(ctx: typer.Context, doi: Doi, *, common: Common) -> None:
    """Show one work."""

    async def action(client: CrossrefClient, output: Output) -> int:
        work = await client.works.get(doi)
        if work is None:
            output.message(f"not found: {doi}")
            return EXIT_NOT_FOUND
        output.one(work, work_panel(work), ("works", "get", work.doi))
        return 0

    run(ctx, common, action)


@works_app.command("exists")
@with_options()
def exists(ctx: typer.Context, doi: Doi, *, common: Common) -> None:
    """Tell whether a DOI is registered with Crossref (exit 0 or 1)."""

    async def action(client: CrossrefClient, output: Output) -> int:
        found = await client.works.exists(doi)
        output.fact(
            {"doi": normalize_doi(doi), "exists": found},
            "yes" if found else "no",
            ("works", "exists", normalize_doi(doi)),
        )
        return 0 if found else EXIT_NOT_FOUND

    run(ctx, common, action)


@works_app.command("agency")
@with_options()
def agency(ctx: typer.Context, doi: Doi, *, common: Common) -> None:
    """Show the registration agency of a DOI."""

    async def action(client: CrossrefClient, output: Output) -> int:
        found = await client.works.agency(doi)
        if found is None:
            output.message(f"not found: {doi}")
            return EXIT_NOT_FOUND
        label = found.agency.label or found.agency.id if found.agency else None
        output.one(
            found,
            f"{found.doi}: {label or 'unknown agency'}",
            ("works", "agency", found.doi),
        )
        return 0

    run(ctx, common, action)


@works_app.command("search")
@with_options(query=True, sortable=True)
def search(
    ctx: typer.Context,
    *,
    rows: Annotated[
        int,
        typer.Option("--rows", help="Rows of the page, 1..1000."),
    ] = 20,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Rows to skip; offset + rows ≤ 10000."),
    ] = 0,
    common: Common,
    query: QueryInput,
) -> None:
    """Search works: one page."""

    async def action(client: CrossrefClient, output: Output) -> int:
        works_query = build_works_query(query.options)
        page = await _target(client, query.journal).search(
            works_query,
            rows=rows,
            offset=offset,
        )
        render = [
            works_table(page.items),
            *(facet_table(facet) for facet in page.facets),
        ]
        output.page(
            page,
            render,
            ("works", "search", works_query.fingerprint()[:8]),
            client.pool,
        )
        return 0

    run(ctx, common, action)


@works_app.command("iterate")
@with_options(query=True, sortable=True)
def iterate(  # ruff: ignore[too-many-arguments] -- every option is named on the command line
    ctx: typer.Context,
    *,
    max_items: Annotated[
        int | None,
        typer.Option(
            "--max",
            help=f"Records to take; {DEFAULT_WALK} by default.",
            show_default=False,
        ),
    ] = None,
    all_items: Annotated[
        bool,
        typer.Option("--all", help="Walk every matching record."),
    ] = False,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Rows per request, 1..1000."),
    ] = 1000,
    common: Common,
    query: QueryInput,
) -> None:
    """Walk works with the cursor."""

    async def action(client: CrossrefClient, output: Output) -> int:
        works_query = build_works_query(query.options)
        limit = None if all_items else max_items or DEFAULT_WALK
        records = _target(client, query.journal).iterate(
            works_query,
            max_items=limit,
            page_size=min(page_size, limit) if limit else page_size,
        )
        shown = await output.walk(
            records,
            works_table,
            ("works", "iterate", works_query.fingerprint()[:8]),
        )
        if (
            not output.as_json
            and limit is not None
            and shown == limit
            and max_items is None
        ):
            output.message(f"showed {shown}; --max N or --all for more")
        return 0

    run(ctx, common, action)


@works_app.command("sample")
@with_options(query=True)
def sample(
    ctx: typer.Context,
    *,
    size: Annotated[int, typer.Option("--size", help="Random records, 1..100.")] = 10,
    common: Common,
    query: QueryInput,
) -> None:
    """Show random works matching the query."""

    async def action(client: CrossrefClient, output: Output) -> int:
        works_query = build_works_query(query.options)
        works = await _target(client, query.journal).sample(works_query, size=size)
        output.records(
            works,
            works_table(works),
            ("works", "sample", works_query.fingerprint()[:8]),
        )
        return 0

    run(ctx, common, action)


@works_app.command("filters")
def filters(
    *,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="JSON even in a terminal."),
    ] = False,
) -> None:
    """List every filter --filter takes."""
    specs = list(filter_specs().values())
    console = Console()
    if as_json or not console.is_terminal:
        write_document(
            sys.stdout,
            [
                {
                    "name": spec.name,
                    "kind": spec.kind,
                    "repeatable": spec.many,
                    "choices": list(spec.choices),
                }
                for spec in specs
            ],
        )
        return
    table = Table(title=f"{len(specs)} filters of /works")
    table.add_column("--filter name", style="cyan", no_wrap=True)
    table.add_column("Value")
    table.add_column("Repeat", justify="center")
    for spec in specs:
        value = ", ".join(spec.choices) if spec.choices else spec.kind
        table.add_row(spec.name, value, "yes" if spec.many else "")
    console.print(table)
