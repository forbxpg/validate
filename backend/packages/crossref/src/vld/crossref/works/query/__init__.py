"""The works query: text, field queries, the filter catalogue, sort, select, facets."""

from __future__ import annotations

from ._enums import (
    FullTextApplication,
    FunderDoiAssertedBy,
    LicenseVersion,
    Order,
    WorkFacet,
    WorkField,
    WorksSort,
    WorkType,
)
from ._filter import WorksFilter
from ._query import FACET_MAX, FIELD_QUERIES, WorksQuery

__all__ = (
    "FACET_MAX",
    "FIELD_QUERIES",
    "FullTextApplication",
    "FunderDoiAssertedBy",
    "LicenseVersion",
    "Order",
    "WorkFacet",
    "WorkField",
    "WorkType",
    "WorksFilter",
    "WorksQuery",
    "WorksSort",
)
