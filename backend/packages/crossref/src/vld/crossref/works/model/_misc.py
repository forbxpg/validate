"""Smaller parts of a work: ISSN types, issue, event, review, references and more."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from vld.crossref.models import (
    CleanStrList,
    CrossrefDate,
    CrossrefModel,
    Doi,
    OptBool,
    OptStr,
    lenient,
)


class IssnType(CrossrefModel):
    """An ISSN or ISBN with its kind.

    Attributes:
        type: str | None - ``print`` or ``electronic``.
        value: str | None - The number as Crossref sends it.

    """

    type: OptStr = None
    value: OptStr = None


class JournalIssue(CrossrefModel):
    """The issue a work appeared in.

    Attributes:
        issue: str | None - Issue number.
        published_print: PartialDate | None - Print date of the issue.
        published_online: PartialDate | None - Online date of the issue.

    """

    issue: OptStr = None
    published_print: CrossrefDate = Field(default=None, alias="published-print")
    published_online: CrossrefDate = Field(default=None, alias="published-online")


class Event(CrossrefModel):
    """The conference or other event of a work.

    Attributes:
        name: str | None - Name.
        location: str | None - Place.
        acronym: str | None - Acronym.
        number: str | None - Number of the event.
        theme: str | None - Theme.
        sponsor: tuple[str, ...] - Sponsors.
        start: PartialDate | None - First day.
        end: PartialDate | None - Last day.

    """

    name: OptStr = None
    location: OptStr = None
    acronym: OptStr = None
    number: OptStr = None
    theme: OptStr = None
    sponsor: CleanStrList = ()
    start: CrossrefDate = None
    end: CrossrefDate = None


class Review(CrossrefModel):
    """Peer review details of a work of type ``peer-review``.

    Attributes:
        type: str | None - Kind of review.
        running_number: str | None - Number of the review.
        revision_round: str | None - Round.
        stage: str | None - ``pre-publication`` or ``post-publication``.
        competing_interest_statement: str | None - Statement of the reviewer.
        recommendation: str | None - Recommendation.
        language: str | None - Language.

    """

    type: OptStr = None
    running_number: OptStr = Field(default=None, alias="running-number")
    revision_round: OptStr = Field(default=None, alias="revision-round")
    stage: OptStr = None
    competing_interest_statement: OptStr = Field(
        default=None,
        alias="competing-interest-statement",
    )
    recommendation: OptStr = None
    language: OptStr = None


class StandardsBody(CrossrefModel):
    """The body that issued a standard.

    Attributes:
        name: str | None - Name.
        acronym: str | None - Acronym.

    """

    name: OptStr = None
    acronym: OptStr = None


class ContentDomain(CrossrefModel):
    """Crossmark domains where the content appears.

    Attributes:
        domain: tuple[str, ...] - Domains.
        crossmark_restriction: bool | None - Whether Crossmark is restricted to them.

    """

    domain: CleanStrList = ()
    crossmark_restriction: OptBool = Field(default=None, alias="crossmark-restriction")


class FreeToRead(CrossrefModel):
    """When a work is free to read.

    Attributes:
        start_date: PartialDate | None - From.
        end_date: PartialDate | None - Until.

    """

    start_date: CrossrefDate = Field(default=None, alias="start-date")
    end_date: CrossrefDate = Field(default=None, alias="end-date")


class Reference(CrossrefModel):
    """One reference of a work, as the publisher deposited it.

    Attributes:
        key: str | None - Key of the reference.
        doi: str | None - DOI of the cited work.
        doi_asserted_by: str | None - ``crossref`` or ``publisher``.
        unstructured: str | None - The reference as one text.
        article_title: str | None - Title of the cited article.
        journal_title: str | None - Title of its journal.
        volume_title: str | None - Title of its volume.
        series_title: str | None - Title of its series.
        author: str | None - First author.
        year: str | None - Year.
        volume: str | None - Volume.
        issue: str | None - Issue.
        first_page: str | None - First page.
        edition: str | None - Edition.
        component: str | None - Component.
        standard_designator: str | None - Designator of a standard.
        standards_body: str | None - Body of a standard.
        isbn: str | None - ISBN.
        isbn_type: str | None - Kind of the ISBN.
        issn: str | None - ISSN.
        issn_type: str | None - Kind of the ISSN.

    """

    key: OptStr = None
    doi: OptStr = Field(default=None, alias="DOI")
    doi_asserted_by: OptStr = Field(default=None, alias="doi-asserted-by")
    unstructured: OptStr = None
    article_title: OptStr = Field(default=None, alias="article-title")
    journal_title: OptStr = Field(default=None, alias="journal-title")
    volume_title: OptStr = Field(default=None, alias="volume-title")
    series_title: OptStr = Field(default=None, alias="series-title")
    author: OptStr = None
    year: OptStr = None
    volume: OptStr = None
    issue: OptStr = None
    first_page: OptStr = Field(default=None, alias="first-page")
    edition: OptStr = None
    component: OptStr = None
    standard_designator: OptStr = Field(default=None, alias="standard-designator")
    standards_body: OptStr = Field(default=None, alias="standards-body")
    isbn: OptStr = None
    isbn_type: OptStr = Field(default=None, alias="isbn-type")
    issn: OptStr = None
    issn_type: OptStr = Field(default=None, alias="issn-type")


class Agency(CrossrefModel):
    """A DOI registration agency.

    Attributes:
        id: str | None - Identifier, such as ``crossref`` or ``datacite``.
        label: str | None - Name to show.

    """

    id: OptStr = None
    label: OptStr = None


class WorkAgency(CrossrefModel):
    """The agency a DOI is registered with.

    Attributes:
        doi: str - The DOI.
        agency: Agency | None - The agency.

    """

    doi: Doi = Field(alias="DOI")
    agency: Annotated[Agency | None, lenient(None)] = None
