"""The catalogue of the works routes against the lists Crossref gave on 2026-09-26.

The lists in ``catalogue_lists`` are copied from Crossref's own validation
messages; the live tests compare them with Crossref again.
"""

from __future__ import annotations

from catalogue_lists import (
    LIVE_FACETS,
    LIVE_FIELD_QUERIES,
    LIVE_FILTERS,
    LIVE_SELECT,
    LIVE_SORT,
    LIVE_TYPES,
)

from vld.crossref import WorkFacet, WorkField, WorksFilter, WorksSort, WorkType
from vld.crossref.works.query import FIELD_QUERIES


def test_every_filter_of_crossref_is_a_field() -> None:
    """The 90 filters, no more and no fewer."""
    names = {
        field.serialization_alias or name
        for name, field in WorksFilter.model_fields.items()
    }

    assert names == set(LIVE_FILTERS)


def test_every_field_query_of_crossref_is_a_field() -> None:
    """The 21 field queries."""
    assert {name.replace("_", "-") for name in FIELD_QUERIES} == set(LIVE_FIELD_QUERIES)


def test_the_enums_hold_exactly_the_values_of_crossref() -> None:
    """select, facets, sort and types, as Crossref accepts them."""
    assert {field.value for field in WorkField} == set(LIVE_SELECT)
    assert {facet.value for facet in WorkFacet} == set(LIVE_FACETS)
    assert {sort.value for sort in WorksSort} == set(LIVE_SORT)
    assert {kind.value for kind in WorkType} == set(LIVE_TYPES)
