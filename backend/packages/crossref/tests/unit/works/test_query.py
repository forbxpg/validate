"""A works query renders into Crossref parameters and refuses its own mistakes."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from vld.crossref import (
    CrossrefQueryError,
    LicenseVersion,
    Order,
    PartialDate,
    WorkFacet,
    WorkField,
    WorksFilter,
    WorksQuery,
    WorksSort,
    WorkType,
)


def test_an_empty_query_lists_everything() -> None:
    """No parameters at all."""
    assert WorksQuery().params() == {}


def test_text_and_field_queries_render_by_their_crossref_names() -> None:
    """Query and query.<kebab-name>; text is stripped."""
    query = WorksQuery(text="  graphene ", author="Ivanov", container_title="Phys Rev")

    assert query.params() == {
        "query": "graphene",
        "query.author": "Ivanov",
        "query.container-title": "Phys Rev",
    }


def test_blank_text_is_no_text() -> None:
    """A blank search box does not search for spaces."""
    assert WorksQuery(text="   ").params() == {}


@pytest.mark.parametrize(
    ("filters", "rendered"),
    [
        (WorksFilter(from_pub_date=PartialDate(2020)), "from-pub-date:2020"),
        (WorksFilter(from_pub_date=PartialDate(2020, 5)), "from-pub-date:2020-05"),
        (WorksFilter(until_pub_date=date(2021, 5, 1)), "until-pub-date:2021-05-01"),
        (
            WorksFilter(
                from_created_date=datetime(
                    2024,
                    1,
                    1,
                    15,
                    tzinfo=timezone(timedelta(hours=3)),
                ),
            ),
            "from-created-date:2024-01-01T12:00:00",
        ),
        (
            WorksFilter(has_orcid=True, is_update=False),
            "has-orcid:true,is-update:false",
        ),
        (WorksFilter(type=WorkType.JOURNAL_ARTICLE), "type:journal-article"),
        (
            WorksFilter(license_version=LicenseVersion.VOR, license_delay=0),
            "license.version:vor,license.delay:0",
        ),
        (WorksFilter(member=[311, 16]), "member:311,member:16"),
        (WorksFilter(issn=["0031 9007", "1079-7114"]), "issn:0031-9007,issn:1079-7114"),
        (WorksFilter(doi="https://doi.org/10.1103/X"), "doi:10.1103/x"),
        (
            WorksFilter(orcid="https://orcid.org/0000-0002-1825-0097"),
            "orcid:0000-0002-1825-0097",
        ),
        (WorksFilter(ror_id="https://ror.org/05qwgg493"), "ror-id:05qwgg493"),
        (WorksFilter(prefix=" 10.1103 "), "prefix:10.1103"),
    ],
)
def test_each_kind_of_filter_value_renders_as_crossref_reads_it(
    filters: WorksFilter,
    rendered: str,
) -> None:
    """Dates keep their precision, identifiers are normalized, repeats stay in order."""
    assert WorksQuery(filter=filters).params() == {"filter": rendered}


def test_filters_render_in_the_order_of_the_catalogue() -> None:
    """The order does not depend on the order of the arguments: equal queries, equal keys."""
    first = WorksQuery(
        filter=WorksFilter(has_orcid=True, from_pub_date=PartialDate(2020)),
    )
    second = WorksQuery(
        filter=WorksFilter(from_pub_date=PartialDate(2020), has_orcid=True),
    )

    assert first.params()["filter"] == "from-pub-date:2020,has-orcid:true"
    assert first.fingerprint() == second.fingerprint()
    assert first.fingerprint() != WorksQuery().fingerprint()


def test_sort_select_and_facets_render_sorted() -> None:
    """Select and facet are sorted by name; a facet without a count asks for all values."""
    query = WorksQuery(
        sort=WorksSort.PUBLISHED,
        order=Order.ASC,
        select=frozenset({WorkField.TITLE, WorkField.DOI}),
        facets={WorkFacet.TYPE_NAME: 5, WorkFacet.ISSN: None},
    )

    assert query.params() == {
        "sort": "published",
        "order": "asc",
        "select": "DOI,title",
        "facet": "issn:*,type-name:5",
    }


def test_select_renders_in_one_order_whatever_the_set_order() -> None:
    """A set has no order; the rendered list is sorted, so equal queries match."""
    query = WorksQuery(select=frozenset(WorkField))

    assert query.params()["select"] == ",".join(
        sorted(field.value for field in WorkField),
    )


def test_select_accepts_known_names_as_strings() -> None:
    """A field name coming from a UI is enough."""
    query = WorksQuery.model_validate({"select": ["DOI", "container-title"]})

    assert query.select == frozenset({WorkField.DOI, WorkField.CONTAINER_TITLE})


@pytest.mark.parametrize(
    "arguments",
    [
        {"order": Order.ASC},
        {"facets": {WorkFacet.TYPE_NAME: 0}},
        {"facets": {WorkFacet.TYPE_NAME: 1001}},
        {"auther": "Ivanov"},
        {"text": "x" * 1001},
        {"select": ["no-such-field"]},
    ],
    ids=[
        "order-without-sort",
        "facet-zero",
        "facet-too-many",
        "typo",
        "too-long",
        "unknown-select",
    ],
)
def test_a_query_that_contradicts_itself_is_refused(
    arguments: dict[str, object],
) -> None:
    """Every mistake is a CrossrefQueryError before any request."""
    with pytest.raises(CrossrefQueryError):
        _ = WorksQuery.model_validate(arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        {"issn": "0031-9008"},
        {"doi": "not-a-doi"},
        {"orcid": "0000-0002-1825-0098"},
        {"container_title": "Physics, Letters"},
        {"from_created_date": datetime(2024, 1, 1)},  # ruff: ignore[call-datetime-without-tzinfo] -- the naive value is the case
        {"license_delay": -1},
        {"from_pub_date": date(2022, 1, 1), "until_pub_date": PartialDate(2021)},
        {"from_pub_dat": PartialDate(2021)},
    ],
    ids=["issn", "doi", "orcid", "comma", "naive", "negative", "inverted", "typo"],
)
def test_a_filter_crossref_would_misread_is_refused(
    arguments: dict[str, object],
) -> None:
    """Bad identifiers, commas, naive moments and empty ranges never reach Crossref."""
    with pytest.raises(CrossrefQueryError):
        _ = WorksFilter.model_validate(arguments)


def test_a_range_within_one_partial_date_is_allowed() -> None:
    """From 2021 until 2021 means the whole year."""
    query = WorksQuery(
        filter=WorksFilter(
            from_pub_date=PartialDate(2021),
            until_pub_date=PartialDate(2021),
        ),
    )

    assert query.params() == {"filter": "from-pub-date:2021,until-pub-date:2021"}


def test_a_query_is_an_immutable_value() -> None:
    """A query is a value."""
    query = WorksQuery(text="x")

    with pytest.raises(ValidationError, match="frozen"):
        query.text = "y"
    assert query == WorksQuery(text="x")
