"""A bad field degrades, a record without identity is dropped, the rest stays."""

from __future__ import annotations

from typing import Annotated

from structlog.testing import capture_logs

from vld.crossref.models import (
    CleanStrList,
    CrossrefModel,
    StrList,
    lenient,
    parse_item,
)


class _Author(CrossrefModel):
    family: str


class _Record(CrossrefModel):
    key: str
    authors: Annotated[tuple[_Author, ...], lenient(())] = ()
    count: Annotated[int | None, lenient(None)] = None
    tags: StrList = ()
    names: CleanStrList = ()


def test_a_malformed_field_degrades_and_the_record_stays() -> None:
    """One bad author list does not cost the record."""
    with capture_logs() as logs:
        record = parse_item(
            _Record,
            {"key": "a", "authors": [{"given": "x"}], "count": 3},
            id_key="key",
        )

    assert record is not None
    assert record.authors == ()
    assert record.count == 3
    assert logs == [
        {
            "event": "crossref_field_degraded",
            "field": "authors",
            "record": "a",
            "error": "Field required",
            "log_level": "warning",
        },
    ]


def test_null_reads_as_empty_without_a_warning() -> None:
    """Crossref sends null for what it does not have; that is not a defect."""
    with capture_logs() as logs:
        record = parse_item(
            _Record,
            {"key": "a", "authors": None, "count": None},
            id_key="key",
        )

    assert record is not None
    assert (record.authors, record.count) == ((), None)
    assert logs == []


def test_a_record_without_identity_is_dropped_with_a_warning() -> None:
    """A strict identity field that fails drops only that record."""
    with capture_logs() as logs:
        record = parse_item(_Record, {"count": 1}, id_key="key")

    assert record is None
    assert logs[0]["event"] == "crossref_item_dropped"
    assert logs[0]["model"] == "_Record"


def test_string_lists_accept_a_single_string_and_null() -> None:
    """One string is a list of one; null is an empty list."""
    assert _Record.model_validate({"key": "a", "tags": "x"}).tags == ("x",)
    assert _Record.model_validate({"key": "a", "tags": None}).tags == ()


def test_clean_string_lists_drop_nulls_blanks_and_non_strings() -> None:
    """Only real strings remain."""
    record = _Record.model_validate({"key": "a", "names": ["a", None, " ", 3, "b"]})

    assert record.names == ("a", "b")


def test_unknown_fields_are_ignored() -> None:
    """A field Crossref adds tomorrow breaks nothing."""
    assert _Record.model_validate({"key": "a", "brand-new": {"x": 1}}).key == "a"
