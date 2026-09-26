"""The Work model on recorded answers of Crossref."""

from __future__ import annotations

from typing import cast

from crossref_support import fixture
from structlog.testing import capture_logs

from vld.crossref import PartialDate, Work, WorkType
from vld.crossref.works._list import parse_work


def _work(name: str) -> Work:
    body = cast("dict[str, object]", fixture(name))
    work = parse_work(body["message"])
    assert work is not None
    return work


def test_a_rich_article_is_read_whole_without_degradation() -> None:
    """Authors with ORCID and ROR, licenses, funders, references, relations."""
    with capture_logs() as logs:
        work = _work("work_rich")

    assert logs == []
    assert work.doi == "10.7554/elife.85324"
    assert work.type is WorkType.JOURNAL_ARTICLE
    assert work.journal_title == "eLife"
    assert work.issn == ("2050-084X",)
    assert work.issn_electronic == "2050-084X"
    assert work.issued == PartialDate(2023, 3, 7)
    assert work.year == 2023
    assert work.author[0].display_name == "Chi Zhang"
    assert work.author[0].orcid == "0000-0003-1288-9006"
    assert len(work.reference) == 87
    assert work.license
    assert work.funder
    assert "has-preprint" in work.relation
    assert work.created is not None
    assert work.created.date_time.tzinfo is not None


def test_a_date_known_to_the_month_stays_a_month() -> None:
    """November 1830, not November 1st."""
    work = _work("work_partial_date")

    assert work.issued == PartialDate(1830, 11)
    assert work.issued is not None
    assert work.issued.precision() == "month"


def test_a_book_chapter_keeps_its_isbns_by_kind() -> None:
    """ISBNs with print and electronic kinds."""
    work = _work("work_book_chapter")

    assert work.type is WorkType.BOOK_CHAPTER
    assert {entry.type for entry in work.isbn_type} == {"print", "electronic"}
    assert work.issued == PartialDate(2023)


def test_a_preprint_is_posted_content() -> None:
    """A preprint is read with its posting date."""
    work = _work("work_posted_content")

    assert work.type is WorkType.POSTED_CONTENT
    assert work.posted is not None


def test_a_malformed_work_degrades_field_by_field() -> None:
    """Broken fields become empty with a warning each; the work and its good fields stay."""
    with capture_logs() as logs:
        work = _work("work_malformed_handmade")

    assert work.doi == "10.7554/elife.85324"
    assert work.author == ()
    assert work.published is None
    assert work.reference == ()
    assert work.issn == ("2050-084X",)
    assert work.title == ("A title",)
    assert work.volume == "12"
    degraded = {
        entry["field"] for entry in logs if entry["event"] == "crossref_field_degraded"
    }
    assert degraded == {"author", "published", "issn"}
    assert all(entry["record"] == "10.7554/elife.85324" for entry in logs)


def test_an_unknown_type_is_kept_as_a_string() -> None:
    """A type Crossref adds later is not lost."""
    work = Work.model_validate({"DOI": "10.1000/a", "type": "hologram"})

    assert work.type == "hologram"
