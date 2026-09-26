"""Options of the command line become the query Crossref gets."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vld.crossref import CrossrefQueryError, PartialDate, WorkFacet, WorkType
from vld.crossref.cli._query import (
    WorksOptions,
    build_works_query,
    filter_specs,
    parse_date,
    parse_facets,
    parse_filters,
)

pytestmark = pytest.mark.usefixtures("isolated")


def test_every_filter_of_crossref_has_a_spec() -> None:
    """All 90 filters, by their Crossref names."""
    specs = filter_specs()

    assert len(specs) == 90
    assert specs["from-pub-date"].kind == "date"
    assert specs["from-index-date"].kind == "moment"
    assert specs["has-orcid"].kind == "yes/no"
    assert specs["issn"].many
    assert "journal-article" in specs["type"].choices


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("2024", PartialDate(2024)),
        ("2024-05", PartialDate(2024, 5)),
        ("2024-05-17", PartialDate(2024, 5, 17)),
    ],
)
def test_a_date_keeps_the_precision_given(text: str, date: PartialDate) -> None:
    """No month or day is invented."""
    assert parse_date(text) == date


@pytest.mark.parametrize("text", ["20x", "2024-13", "2024-02-30", "24", ""])
def test_a_bad_date_is_refused(text: str) -> None:
    """Before any request."""
    with pytest.raises(CrossrefQueryError, match="not a date"):
        _ = parse_date(text)


def test_filters_are_read_by_crossref_name_and_repeats_or() -> None:
    """Repeated many-valued filters become lists; values are converted."""
    values = parse_filters(
        [
            "from-online-pub-date=2024-05",
            "issn=0031-9007",
            "issn=1079-7114",
            "has-orcid=yes",
        ],
    )

    assert values == {
        "from_online_pub_date": PartialDate(2024, 5),
        "issn": ["0031-9007", "1079-7114"],
        "has_orcid": True,
    }


def test_a_deposit_moment_needs_its_zone() -> None:
    """A naive time would be read in the zone of the machine."""
    values = parse_filters(["from-index-date=2024-05-17T10:00:00Z"])

    assert values == {"from_index_date": datetime(2024, 5, 17, 10, tzinfo=UTC)}
    with pytest.raises(CrossrefQueryError, match="zone"):
        _ = parse_filters(["from-index-date=2024-05-17T10:00:00"])


@pytest.mark.parametrize(
    ("pair", "problem"),
    [
        ("from-pub-date", "name=value"),
        ("no-such-filter=1", "unknown filter"),
        ("has-orcid=maybe", "yes or no"),
    ],
)
def test_a_bad_filter_is_refused(pair: str, problem: str) -> None:
    """With a message that says what to fix."""
    with pytest.raises(CrossrefQueryError, match=problem):
        _ = parse_filters([pair])


def test_a_single_filter_given_twice_is_refused() -> None:
    """Only many-valued filters OR."""
    with pytest.raises(CrossrefQueryError, match="one value"):
        _ = parse_filters(["from-pub-date=2020", "from-pub-date=2021"])


def test_facets_take_an_optional_count() -> None:
    """A facet is a name, or a name and a count."""
    assert parse_facets(["type-name:5", "publisher-name"]) == {
        WorkFacet.TYPE_NAME: 5,
        WorkFacet.PUBLISHER_NAME: None,
    }
    with pytest.raises(CrossrefQueryError, match="unknown facet"):
        _ = parse_facets(["nope"])
    with pytest.raises(CrossrefQueryError, match="number"):
        _ = parse_facets(["type-name:x"])


def test_options_become_one_query() -> None:
    """Text, field queries, shortcuts and --filter meet in one WorksQuery."""
    query = build_works_query(
        WorksOptions(
            text="graphene",
            fields={"author": "Geim", "title": None},
            shortcuts={
                "type": [WorkType.JOURNAL_ARTICLE],
                "from_pub_date": "2010",
                "issn": ["0031-9007"],
                "has_orcid": None,
            },
            filters=["issn=1079-7114", "has-abstract=true"],
        ),
    )

    assert query.params() == {
        "query": "graphene",
        "query.author": "Geim",
        "filter": query.filter.render(),
    }
    rendered = query.filter.render() or ""
    assert "type:journal-article" in rendered
    assert "from-pub-date:2010" in rendered
    assert "issn:0031-9007" in rendered
    assert "issn:1079-7114" in rendered
    assert "has-abstract:true" in rendered


def test_a_shortcut_and_a_filter_of_one_single_filter_clash() -> None:
    """--from and --filter from-pub-date=… cannot both win."""
    with pytest.raises(CrossrefQueryError, match="twice"):
        _ = build_works_query(
            WorksOptions(
                shortcuts={"from_pub_date": "2010"},
                filters=["from-pub-date=2011"],
            ),
        )


def test_an_unknown_field_query_is_refused() -> None:
    """A typo in the command's own code must not pass silently."""
    with pytest.raises(CrossrefQueryError, match="unknown field"):
        _ = build_works_query(WorksOptions(fields={"authr": "x"}))
