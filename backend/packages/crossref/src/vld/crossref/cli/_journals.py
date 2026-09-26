"""`vld-crossref journals`: a journal by ISSN, searches and walks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vld.crossref import JournalsQuery
from vld.crossref.ids import normalize_issn

from ._options import Common, with_options
from ._render import journal_panel, journals_table
from ._runtime import EXIT_NOT_FOUND, Output, run

if TYPE_CHECKING:
    from vld.crossref import CrossrefClient

DEFAULT_WALK = 100
"""Journals a walk takes without `--max` or `--all`."""

journals_app = typer.Typer(
    name="journals",
    help=(
        "Journals: get one by ISSN, search, walk. "
        "Their works: `works … --journal ISSN`."
    ),
    no_args_is_help=True,
)

Issn = Annotated[str, typer.Argument(help="ISSN: 0031-9007, 0031 9007 or 00319007.")]
Text = Annotated[
    str | None,
    typer.Argument(help="Free text to search for.", show_default=False),
]


@journals_app.command("get")
@with_options()
def get(ctx: typer.Context, issn: Issn, *, common: Common) -> None:
    """Show one journal."""

    async def action(client: CrossrefClient, output: Output) -> int:
        journal = await client.journals.get(issn)
        if journal is None:
            output.message(f"not found: {issn}")
            return EXIT_NOT_FOUND
        output.one(
            journal,
            journal_panel(journal),
            ("journals", "get", normalize_issn(issn)),
        )
        return 0

    run(ctx, common, action)


@journals_app.command("exists")
@with_options()
def exists(ctx: typer.Context, issn: Issn, *, common: Common) -> None:
    """Tell whether Crossref knows a journal (exit 0 or 1)."""

    async def action(client: CrossrefClient, output: Output) -> int:
        found = await client.journals.exists(issn)
        output.fact(
            {"issn": normalize_issn(issn), "exists": found},
            "yes" if found else "no",
            ("journals", "exists", normalize_issn(issn)),
        )
        return 0 if found else EXIT_NOT_FOUND

    run(ctx, common, action)


@journals_app.command("search")
@with_options()
def search(
    ctx: typer.Context,
    text: Text = None,
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
) -> None:
    """Search journals: one page."""

    async def action(client: CrossrefClient, output: Output) -> int:
        query = JournalsQuery(text=text)
        page = await client.journals.search(query, rows=rows, offset=offset)
        output.page(
            page,
            [journals_table(page.items)],
            ("journals", "search", query.fingerprint()[:8]),
            client.pool,
        )
        return 0

    run(ctx, common, action)


@journals_app.command("iterate")
@with_options()
def iterate(  # ruff: ignore[too-many-arguments] -- every option is named on the command line
    ctx: typer.Context,
    text: Text = None,
    *,
    max_items: Annotated[
        int | None,
        typer.Option(
            "--max",
            help=f"Journals to take; {DEFAULT_WALK} by default.",
            show_default=False,
        ),
    ] = None,
    all_items: Annotated[
        bool,
        typer.Option("--all", help="Walk every journal."),
    ] = False,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Rows per request, 1..1000."),
    ] = 1000,
    common: Common,
) -> None:
    """Walk journals with the cursor."""

    async def action(client: CrossrefClient, output: Output) -> int:
        query = JournalsQuery(text=text)
        limit = None if all_items else max_items or DEFAULT_WALK
        records = client.journals.iterate(
            query,
            max_items=limit,
            page_size=min(page_size, limit) if limit else page_size,
        )
        shown = await output.walk(
            records,
            journals_table,
            ("journals", "iterate", query.fingerprint()[:8]),
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
