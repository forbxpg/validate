"""The `vld-crossref` application: the works and journals command groups."""

from __future__ import annotations

import typer

from ._journals import journals_app
from ._works import works_app

app = typer.Typer(
    name="vld-crossref",
    help="Ask Crossref from a terminal: works and journals.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(works_app)
app.add_typer(journals_app)
