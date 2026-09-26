"""A works query: text, field queries, filters, sort, select and facets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Self, cast, override

from pydantic import Field, model_validator

from vld.crossref.errors import CrossrefQueryError
from vld.crossref.models import QueryModel, Text

from ._enums import Order, WorkFacet, WorkField, WorksSort
from ._filter import WorksFilter

FACET_MAX = 1000
"""Most values a facet returns."""

FIELD_QUERIES = (
    "affiliation",
    "author",
    "bibliographic",
    "chair",
    "container_title",
    "contributor",
    "degree",
    "description",
    "editor",
    "event_acronym",
    "event_location",
    "event_name",
    "event_sponsor",
    "event_theme",
    "funder_name",
    "publisher_location",
    "publisher_name",
    "standards_body_acronym",
    "standards_body_name",
    "title",
    "translator",
)
"""Fields searched by ``query.<name>``, as Crossref listed them (21)."""


class WorksQuery(QueryModel):
    """What to look for among works; paging is an argument of the method, not here.

    Attributes:
        text: str | None - Free text (``query``).
        filter: WorksFilter - Filters.
        sort: WorksSort | None - Sort field.
        order: Order | None - Sort direction; needs ``sort``.
        select: frozenset[WorkField] - Fields to return; empty for all.
        facets: Mapping[WorkFacet, int | None] - Facets and how many values each
            returns; None asks for as many as Crossref gives (``*``).

    """

    text: Text = None
    affiliation: Text = None
    author: Text = None
    bibliographic: Text = None
    chair: Text = None
    container_title: Text = None
    contributor: Text = None
    degree: Text = None
    description: Text = None
    editor: Text = None
    event_acronym: Text = None
    event_location: Text = None
    event_name: Text = None
    event_sponsor: Text = None
    event_theme: Text = None
    funder_name: Text = None
    publisher_location: Text = None
    publisher_name: Text = None
    standards_body_acronym: Text = None
    standards_body_name: Text = None
    title: Text = None
    translator: Text = None

    filter: WorksFilter = Field(default_factory=WorksFilter)
    sort: WorksSort | None = None
    order: Order | None = None
    select: frozenset[WorkField] = frozenset()
    facets: Mapping[WorkFacet, int | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Refuse an order without a sort and facet counts out of range.

        Returns:
            Self - The query.

        Raises:
            CrossrefQueryError: If the query contradicts itself.

        """
        if self.order is not None and self.sort is None:
            msg = "order needs sort"
            raise CrossrefQueryError(msg)
        for facet, count in self.facets.items():
            if count is not None and not 1 <= count <= FACET_MAX:
                msg = f"facet {facet.value} count must be within 1..{FACET_MAX}"
                raise CrossrefQueryError(msg)
        return self

    def field_queries(self) -> dict[str, str]:
        """The field queries that are set, by their Crossref name.

        Returns:
            dict[str, str] - ``query.<name>`` to text.

        """
        found: dict[str, str] = {}
        for name in FIELD_QUERIES:
            value = cast("object", getattr(self, name))
            if isinstance(value, str):
                found["query." + name.replace("_", "-")] = value
        return found

    @override
    def params(self) -> dict[str, str]:
        """Render the query into Crossref parameters, deterministically.

        Returns:
            dict[str, str] - The parameters; empty for an empty query.

        """
        params: dict[str, str] = {}
        if self.text is not None:
            params["query"] = self.text
        params.update(self.field_queries())
        rendered = self.filter.render()
        if rendered is not None:
            params["filter"] = rendered
        if self.sort is not None:
            params["sort"] = self.sort.value
        if self.order is not None:
            params["order"] = self.order.value
        if self.select:
            params["select"] = ",".join(sorted(field.value for field in self.select))
        if self.facets:
            params["facet"] = ",".join(
                f"{facet.value}:{'*' if count is None else count}"
                for facet, count in sorted(
                    self.facets.items(),
                    key=lambda kv: kv[0].value,
                )
            )
        return params
