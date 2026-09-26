"""Options of the command line turned into queries; pure, no network."""

from __future__ import annotations

import re
import types
import typing
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from vld.crossref.errors import CrossrefQueryError
from vld.crossref.models import PartialDate
from vld.crossref.works.query import (
    FIELD_QUERIES,
    Order,
    WorkFacet,
    WorksFilter,
    WorksQuery,
    WorksSort,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

type ValueKind = Literal["date", "moment", "yes/no", "number", "choice", "text"]

_PARTIAL_DATE = re.compile(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?")
_TRUE = frozenset({"true", "yes", "1"})
_FALSE = frozenset({"false", "no", "0"})
_FACET_SEPARATOR = ":"


@dataclass(frozen=True, slots=True)
class FilterSpec:
    """One filter of Crossref as the command line takes it.

    Attributes:
        name: str - Crossref name, such as `from-pub-date`.
        field: str - Field of `WorksFilter`.
        many: bool - Whether the filter may be repeated (values are ORed).
        kind: ValueKind - What its value is.
        choices: tuple[str, ...] - Allowed values of a `choice` filter.

    """

    name: str
    field: str
    many: bool
    kind: ValueKind
    choices: tuple[str, ...] = ()


def _spec(field: str, annotation: object, name: str) -> FilterSpec:
    origin = typing.cast("object", typing.get_origin(annotation))
    many = typing.cast("str | None", getattr(origin, "__name__", None)) == "_Many"
    arguments = typing.cast("tuple[object, ...]", typing.get_args(annotation))
    members = ((arguments[0],) if many else arguments) or (annotation,)
    kinds: set[object] = {member for member in members if member is not types.NoneType}
    if PartialDate in kinds:
        kind: ValueKind = "moment" if datetime in kinds else "date"
        return FilterSpec(name, field, many, kind)
    if bool in kinds:
        return FilterSpec(name, field, many, "yes/no")
    if int in kinds:
        return FilterSpec(name, field, many, "number")
    enums = [
        member
        for member in kinds
        if isinstance(member, type) and issubclass(member, StrEnum)
    ]
    if enums:
        return FilterSpec(
            name,
            field,
            many,
            "choice",
            tuple(item.value for item in enums[0]),
        )
    return FilterSpec(name, field, many, "text")


def filter_specs() -> dict[str, FilterSpec]:
    """Describe every filter of `WorksFilter`, keyed by its Crossref name.

    Returns:
        dict[str, FilterSpec] - The filters, in the order of the model.

    """
    specs: dict[str, FilterSpec] = {}
    for field, info in WorksFilter.model_fields.items():
        name = info.serialization_alias or field
        specs[name] = _spec(field, info.annotation, name)
    return specs


def parse_date(text: str) -> PartialDate:
    """Read `2024`, `2024-05` or `2024-05-17` with the precision given.

    Args:
        text: str - The date.

    Returns:
        PartialDate - The date.

    Raises:
        CrossrefQueryError: If the text is not a date of one of the three forms.

    """
    match = _PARTIAL_DATE.fullmatch(text.strip())
    if match is None:
        msg = f"not a date: {text!r}; use 2024, 2024-05 or 2024-05-17"
        raise CrossrefQueryError(msg)
    year, month, day = (int(part) if part else None for part in match.groups())
    try:
        if month is not None:
            _ = date(year or 1, month, day or 1)
    except ValueError as error:
        msg = f"not a date: {text!r}"
        raise CrossrefQueryError(msg) from error
    return PartialDate(year or 0, month, day)


def _parse_moment(text: str) -> PartialDate | datetime:
    if "T" not in text:
        return parse_date(text)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        msg = f"not a date and time: {text!r}"
        raise CrossrefQueryError(msg) from error
    if moment.tzinfo is None:
        msg = f"a date and time needs its zone, such as {text}Z or {text}+03:00"
        raise CrossrefQueryError(msg)
    return moment


def _parse_bool(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    msg = f"not yes or no: {text!r}; use true or false"
    raise CrossrefQueryError(msg)


def _convert(spec: FilterSpec, text: str) -> object:
    match spec.kind:
        case "date":
            return parse_date(text)
        case "moment":
            return _parse_moment(text)
        case "yes/no":
            return _parse_bool(text)
        case _:
            return text


def parse_filters(pairs: Sequence[str]) -> dict[str, object]:
    """Read repeated `--filter name=value` options into `WorksFilter` fields.

    Args:
        pairs: Sequence[str] - The options, Crossref names.

    Returns:
        dict[str, object] - Field name → value, or a list for a repeated filter.

    Raises:
        CrossrefQueryError: If a pair has no `=`, a name is unknown, a single
            filter is repeated or a value cannot be read.

    """
    specs = filter_specs()
    values: dict[str, object] = {}
    for pair in pairs:
        name, separator, text = pair.partition("=")
        name = name.strip()
        if not separator or not name:
            msg = f"--filter takes name=value, got {pair!r}"
            raise CrossrefQueryError(msg)
        spec = specs.get(name)
        if spec is None:
            msg = f"unknown filter {name!r}; `vld-crossref works filters` lists them"
            raise CrossrefQueryError(msg)
        value = _convert(spec, text.strip())
        if spec.many:
            previous = values.setdefault(spec.field, [])
            if isinstance(previous, list):
                typing.cast("list[object]", previous).append(value)
        elif spec.field in values:
            msg = f"filter {name!r} takes one value"
            raise CrossrefQueryError(msg)
        else:
            values[spec.field] = value
    return values


def parse_facets(items: Sequence[str]) -> dict[WorkFacet, int | None]:
    """Read `--facet name[:count]` options.

    Args:
        items: Sequence[str] - The options.

    Returns:
        dict[WorkFacet, int | None] - Facet → number of values, None for the default.

    Raises:
        CrossrefQueryError: If a facet name or count is not valid.

    """
    facets: dict[WorkFacet, int | None] = {}
    for item in items:
        name, _, count = item.partition(_FACET_SEPARATOR)
        try:
            facet = WorkFacet(name.strip())
        except ValueError as error:
            known = ", ".join(member.value for member in WorkFacet)
            msg = f"unknown facet {name!r}; known: {known}"
            raise CrossrefQueryError(msg) from error
        if count.strip() and not count.strip().isdigit():
            msg = f"facet count must be a number, got {count!r}"
            raise CrossrefQueryError(msg)
        facets[facet] = int(count) if count.strip() else None
    return facets


@dataclass(frozen=True, slots=True)
class WorksOptions:
    """Everything the query options of a works command carry.

    Attributes:
        text: str | None - Free text.
        fields: Mapping[str, str | None] - Field queries by `WorksQuery` field name.
        shortcuts: Mapping[str, object] - Filter shortcuts by `WorksFilter` field name.
        filters: Sequence[str] - Repeated `--filter name=value`.
        sort: WorksSort | None - Sort field.
        order: Order | None - Sort direction.
        facets: Sequence[str] - Repeated `--facet name[:count]`.

    """

    text: str | None = None
    fields: Mapping[str, str | None] = types.MappingProxyType({})
    shortcuts: Mapping[str, object] = types.MappingProxyType({})
    filters: Sequence[str] = ()
    sort: WorksSort | None = None
    order: Order | None = None
    facets: Sequence[str] = ()


def build_works_query(options: WorksOptions) -> WorksQuery:
    """Assemble the works query of a command.

    A shortcut and a `--filter` of the same filter are combined: many-valued
    filters take both values, a single-valued one refuses the second.

    Args:
        options: WorksOptions - The options of the command.

    Returns:
        WorksQuery - The query.

    Raises:
        CrossrefQueryError: If an option or their combination is not valid.

    """
    unknown = set(options.fields) - set(FIELD_QUERIES)
    if unknown:
        msg = f"unknown field queries: {sorted(unknown)}"
        raise CrossrefQueryError(msg)
    values = parse_filters(options.filters)
    specs = {spec.field: spec for spec in filter_specs().values()}
    many = {field for field, spec in specs.items() if spec.many}
    for field, given in options.shortcuts.items():
        if given is None or given in ((), []):
            continue
        value = _convert(specs[field], given) if isinstance(given, str) else given
        if field in many:
            added = (
                list(typing.cast("Sequence[object]", value))
                if isinstance(value, (list, tuple))
                else [value]
            )
            existing = values.get(field, [])
            values[field] = [*typing.cast("list[object]", existing), *added]
        elif field in values:
            msg = f"filter {field!r} given twice"
            raise CrossrefQueryError(msg)
        else:
            values[field] = value
    fields = {name: value for name, value in options.fields.items() if value}
    return WorksQuery.model_validate(
        {
            "text": options.text,
            **fields,
            "filter": WorksFilter.model_validate(values),
            "sort": options.sort,
            "order": options.order,
            "facets": parse_facets(options.facets),
        },
    )
