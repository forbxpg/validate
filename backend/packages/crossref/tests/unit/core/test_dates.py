"""Dates as precise as Crossref knows them."""

from __future__ import annotations

from datetime import date

import pytest
from structlog.testing import capture_logs

from vld.crossref import PartialDate
from vld.crossref.models import CrossrefDate, CrossrefModel, CrossrefTimestamp


class _Dated(CrossrefModel):
    published: CrossrefDate = None


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        ([[2020]], PartialDate(2020)),
        ([[2020, 5]], PartialDate(2020, 5)),
        ([[2020, 5, 17]], PartialDate(2020, 5, 17)),
        ([[2020, None, 17]], PartialDate(2020)),
        ([[None]], None),
        ([], None),
    ],
)
def test_date_parts_keep_their_precision(
    parts: list[list[int | None]],
    expected: PartialDate | None,
) -> None:
    """A missing month or day stays missing; no first of January is invented."""
    assert (
        _Dated.model_validate({"published": {"date-parts": parts}}).published
        == expected
    )


def test_an_impossible_day_is_dropped_with_a_warning() -> None:
    """February 30th keeps its year and month."""
    with capture_logs() as logs:
        model = _Dated.model_validate({"published": {"date-parts": [[2020, 2, 30]]}})

    assert model.published == PartialDate(2020, 2)
    assert [entry["event"] for entry in logs] == ["crossref_field_degraded"]
    assert logs[0]["field"] == "published"


def test_a_malformed_date_degrades_to_none() -> None:
    """A date of the wrong shape reads as None and says so."""
    with capture_logs() as logs:
        model = _Dated.model_validate({"published": "yesterday"})

    assert model.published is None
    assert logs[0]["event"] == "crossref_field_degraded"


@pytest.mark.parametrize(
    ("value", "earliest", "latest", "precision", "text"),
    [
        (PartialDate(2020), date(2020, 1, 1), date(2020, 12, 31), "year", "2020"),
        (PartialDate(2024, 2), date(2024, 2, 1), date(2024, 2, 29), "month", "2024-02"),
        (PartialDate(2023, 2), date(2023, 2, 1), date(2023, 2, 28), "month", "2023-02"),
        (
            PartialDate(2020, 5, 17),
            date(2020, 5, 17),
            date(2020, 5, 17),
            "day",
            "2020-05-17",
        ),
    ],
)
def test_a_partial_date_spans_every_day_it_may_mean(
    value: PartialDate,
    earliest: date,
    latest: date,
    precision: str,
    text: str,
) -> None:
    """The bounds, the precision and the text follow what is known."""
    assert (value.earliest(), value.latest(), value.precision(), str(value)) == (
        earliest,
        latest,
        precision,
        text,
    )


def test_partial_dates_order_by_year_month_day() -> None:
    """A year sorts before its months, a month before its days."""
    dates = [
        PartialDate(2020, 5, 1),
        PartialDate(2020),
        PartialDate(2019, 12),
        PartialDate(2020, 5),
    ]

    assert sorted(dates) == [
        PartialDate(2019, 12),
        PartialDate(2020),
        PartialDate(2020, 5),
        PartialDate(2020, 5, 1),
    ]


@pytest.mark.parametrize(
    ("year", "month", "day"),
    [(0, None, None), (2020, 13, None), (2020, None, 1), (2021, 2, 29)],
)
def test_an_impossible_partial_date_cannot_be_built(
    year: int,
    month: int | None,
    day: int | None,
) -> None:
    """The constructor refuses what cannot exist."""
    with pytest.raises(ValueError, match=r"range|month|day"):
        _ = PartialDate(year, month, day)


def test_a_timestamp_reads_all_three_forms() -> None:
    """created, deposited and indexed carry parts, an ISO moment and milliseconds."""
    stamp = CrossrefTimestamp.model_validate(
        {
            "date-parts": [[2024, 1, 5]],
            "date-time": "2024-01-05T10:20:30Z",
            "timestamp": 1704450030000,
        },
    )

    assert stamp.parts == PartialDate(2024, 1, 5)
    assert stamp.date_time.tzinfo is not None
    assert stamp.timestamp_ms == 1704450030000
