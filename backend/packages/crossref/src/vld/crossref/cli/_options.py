"""Options shared by the commands, declared once and added to each signature."""

from __future__ import annotations

import functools
import inspect
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from vld.crossref.works.query import FIELD_QUERIES, Order, WorksSort, WorkType

from ._query import WorksOptions

if typing.TYPE_CHECKING:
    from collections.abc import Callable

_OUTPUT = "Output"
_FIELDS = "Field queries"
_FILTERS = "Filters"
_ORDER = "Sort and facets"
_KW = inspect.Parameter.KEYWORD_ONLY


@dataclass(frozen=True, slots=True)
class Common:
    """Options every command takes.

    Attributes:
        mailto: str | None - `--mailto`.
        as_json: bool - `--json`: JSON even in a terminal.
        save_json: bool - `--save-json`: also save the result.
        out_dir: Path | None - `--out-dir`: folder of saved files.
        out: Path | None - `--out`: the saved file itself; implies saving.
        verbose: bool - `-v`: debug logs and tracebacks.

    """

    mailto: str | None = None
    as_json: bool = False
    save_json: bool = False
    out_dir: Path | None = None
    out: Path | None = None
    verbose: bool = False


def _option(name: str, annotation: object, default: object = None) -> inspect.Parameter:
    return inspect.Parameter(name, _KW, default=default, annotation=annotation)


_COMMON = (
    _option(
        "mailto",
        Annotated[
            str | None,
            typer.Option(
                "--mailto",
                help="Address for the polite pool; else CROSSREF_MAILTO.",
                rich_help_panel=_OUTPUT,
            ),
        ],
    ),
    _option(
        "as_json",
        Annotated[
            bool,
            typer.Option(
                "--json",
                help="JSON even in a terminal.",
                rich_help_panel=_OUTPUT,
            ),
        ],
        default=False,
    ),
    _option(
        "save_json",
        Annotated[
            bool,
            typer.Option(
                "--save-json",
                help="Also save the result as JSON.",
                rich_help_panel=_OUTPUT,
            ),
        ],
        default=False,
    ),
    _option(
        "out_dir",
        Annotated[
            Path | None,
            typer.Option(
                "--out-dir",
                help=(
                    "Folder of saved files; "
                    "else CROSSREF_OUTPUT_DIR, else ./crossref-output."
                ),
                rich_help_panel=_OUTPUT,
            ),
        ],
    ),
    _option(
        "out",
        Annotated[
            Path | None,
            typer.Option(
                "--out",
                help="Save into this file (implies --save-json).",
                rich_help_panel=_OUTPUT,
            ),
        ],
    ),
    _option(
        "verbose",
        Annotated[
            bool,
            typer.Option(
                "-v",
                "--verbose",
                help="Debug logs and tracebacks.",
                rich_help_panel=_OUTPUT,
            ),
        ],
        default=False,
    ),
)

_FIELD_PARAMETERS = tuple(
    _option(
        f"q_{field}",
        Annotated[
            str | None,
            typer.Option(
                "--" + field.replace("_", "-"),
                help=f"Search in query.{field.replace('_', '-')}.",
                rich_help_panel=_FIELDS,
            ),
        ],
    )
    for field in FIELD_QUERIES
)

_SHORTCUTS = (
    _option(
        "text",
        Annotated[
            str | None,
            typer.Argument(help="Free text to search for.", show_default=False),
        ],
    ),
    _option(
        "type_",
        Annotated[
            list[WorkType] | None,
            typer.Option(
                "--type",
                metavar="TYPE",
                help=(
                    "Work type, such as journal-article; repeat to OR. "
                    "See `works filters`."
                ),
                rich_help_panel=_FILTERS,
            ),
        ],
    ),
    _option(
        "from_",
        Annotated[
            str | None,
            typer.Option(
                "--from",
                help="Published on or after: 2024, 2024-05 or 2024-05-17.",
                rich_help_panel=_FILTERS,
            ),
        ],
    ),
    _option(
        "until",
        Annotated[
            str | None,
            typer.Option(
                "--until",
                help="Published on or before: 2024, 2024-05 or 2024-05-17.",
                rich_help_panel=_FILTERS,
            ),
        ],
    ),
    *(
        _option(
            name,
            Annotated[
                list[str] | None,
                typer.Option(
                    f"--{name}",
                    help=f"{label}; repeat to OR.",
                    rich_help_panel=_FILTERS,
                ),
            ],
        )
        for name, label in (
            ("issn", "ISSN of the journal"),
            ("orcid", "ORCID iD of a contributor"),
            ("prefix", "DOI prefix"),
            ("member", "Crossref member id"),
        )
    ),
    *(
        _option(
            f"has_{name}",
            Annotated[
                bool | None,
                typer.Option(
                    f"--has-{name}/--no-{name}",
                    help=f"Only works with (or without) {label}.",
                    rich_help_panel=_FILTERS,
                    show_default=False,
                ),
            ],
        )
        for name, label in (("orcid", "an ORCID iD"), ("abstract", "an abstract"))
    ),
    _option(
        "filters",
        Annotated[
            list[str] | None,
            typer.Option(
                "--filter",
                help=(
                    "Any filter as name=value, Crossref names; repeat. "
                    "See `works filters`."
                ),
                rich_help_panel=_FILTERS,
            ),
        ],
    ),
    _option(
        "journal",
        Annotated[
            str | None,
            typer.Option(
                "--journal",
                help="Only works of this journal (ISSN): /journals/{issn}/works.",
                rich_help_panel=_FILTERS,
            ),
        ],
    ),
)

_SORTING = (
    _option(
        "sort",
        Annotated[WorksSort | None, typer.Option("--sort", rich_help_panel=_ORDER)],
    ),
    _option(
        "order",
        Annotated[Order | None, typer.Option("--order", rich_help_panel=_ORDER)],
    ),
    _option(
        "facets",
        Annotated[
            list[str] | None,
            typer.Option(
                "--facet",
                help="Facet as name or name:count; repeat.",
                rich_help_panel=_ORDER,
            ),
        ],
    ),
)


@dataclass(frozen=True, slots=True)
class QueryInput:
    """The query options of a works command, before they become a query.

    Attributes:
        options: WorksOptions - Text, field queries, filters, sort and facets.
        journal: str | None - `--journal`: the ISSN whose works route to use.

    """

    options: WorksOptions
    journal: str | None


def _query_input(values: dict[str, object]) -> QueryInput:
    fields = {field: values.pop(f"q_{field}") for field in FIELD_QUERIES}
    shortcuts: dict[str, object] = {
        "type": values.pop("type_"),
        "from_pub_date": values.pop("from_"),
        "until_pub_date": values.pop("until"),
        "issn": values.pop("issn"),
        "orcid": values.pop("orcid"),
        "prefix": values.pop("prefix"),
        "member": values.pop("member"),
        "has_orcid": values.pop("has_orcid"),
        "has_abstract": values.pop("has_abstract"),
    }
    options = WorksOptions(
        text=typing.cast("str | None", values.pop("text")),
        fields=typing.cast("dict[str, str | None]", fields),
        shortcuts=shortcuts,
        filters=typing.cast("list[str]", values.pop("filters") or []),
        sort=typing.cast("WorksSort | None", values.pop("sort", None)),
        order=typing.cast("Order | None", values.pop("order", None)),
        facets=typing.cast("list[str]", values.pop("facets", None) or []),
    )
    return QueryInput(
        options=options,
        journal=typing.cast("str | None", values.pop("journal")),
    )


def with_options(
    *,
    query: bool = False,
    sortable: bool = False,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Add the shared options to a command and hand them over as objects.

    The command declares its own parameters and receives `common: Common` and,
    with `query=True`, `query: QueryInput`; Typer sees every option in the
    signature, so `--help` lists them.

    Args:
        query: bool - Also add the query options of works.
        sortable: bool - Also add sort, order and facets.

    Returns:
        Callable[[Callable[..., None]], Callable[..., None]] - The decorator.

    """

    def decorate(command: Callable[..., None]) -> Callable[..., None]:
        hints = typing.cast(
            "dict[str, object]",
            typing.get_type_hints(command, include_extras=True),
        )
        own = [
            parameter.replace(
                annotation=hints.get(
                    parameter.name,
                    typing.cast("object", parameter.annotation),
                ),
            )
            for parameter in inspect.signature(command).parameters.values()
            if parameter.name not in {"common", "query"}
        ]
        added = [
            *(_SHORTCUTS if query else ()),
            *(_FIELD_PARAMETERS if query else ()),
            *(_SORTING if sortable else ()),
            *_COMMON,
        ]

        @functools.wraps(command)
        def wrapper(**values: object) -> None:
            common = Common(**{
                parameter.name: values.pop(parameter.name) for parameter in _COMMON
            })  # pyright: ignore[reportArgumentType]
            extra: dict[str, object] = {"common": common}
            if query:
                extra["query"] = _query_input(values)
            command(**values, **extra)

        parameters = [*own, *added]
        wrapper.__signature__ = inspect.Signature(parameters)  # pyright: ignore[reportAttributeAccessIssue]
        wrapper.__annotations__ = {
            parameter.name: typing.cast("object", parameter.annotation)
            for parameter in parameters
        }
        return wrapper

    return decorate
