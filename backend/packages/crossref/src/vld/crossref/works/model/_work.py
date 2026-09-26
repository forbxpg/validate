"""A work: one DOI and everything Crossref knows about it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import Field

from vld.crossref.errors import CrossrefQueryError
from vld.crossref.ids import normalize_issn
from vld.crossref.models import (
    CleanStrList,
    CrossrefDate,
    CrossrefModel,
    CrossrefTimestamp,
    Doi,
    IssnList,
    OptFloat,
    OptInt,
    OptStr,
    PartialDate,
    lenient,
)
from vld.crossref.works.query import WorkType

from ._contributors import Affiliation, Contributor
from ._funding import Funder, Project
from ._links import License, Link, Resources
from ._misc import (
    ContentDomain,
    Event,
    FreeToRead,
    IssnType,
    JournalIssue,
    Reference,
    Review,
    StandardsBody,
)
from ._relations import Assertion, ClinicalTrial, Relation, Update

Contributors = Annotated[tuple[Contributor, ...], lenient(())]
Date = CrossrefDate
Stamp = Annotated[CrossrefTimestamp | None, lenient(None)]


class Work(CrossrefModel):
    """A work of Crossref. Only ``doi`` is strict; every other field degrades alone.

    Attributes:
        doi: str - The DOI, lower case.
        url: str | None - The DOI link.
        type: WorkType | str | None - Type; an unknown type stays a string.
        subtype: str | None - Subtype.
        title: tuple[str, ...] - Titles.
        subtitle: tuple[str, ...] - Subtitles.
        short_title: tuple[str, ...] - Short titles.
        original_title: tuple[str, ...] - Titles in the original language.
        container_title: tuple[str, ...] - Journal, book or proceedings titles.
        short_container_title: tuple[str, ...] - Their short forms.
        group_title: str | None - Group of a posted content.
        issue_title: tuple[str, ...] - Titles of the issue.
        publisher: str | None - Publisher.
        publisher_location: str | None - Its place.
        member: str | None - Crossref member id.
        prefix: str | None - DOI prefix.
        source: str | None - Where the metadata came from.
        issn: tuple[str, ...] - ISSNs, normalized.
        issn_type: tuple[IssnType, ...] - ISSNs with kinds.
        isbn: tuple[str, ...] - ISBNs.
        isbn_type: tuple[IssnType, ...] - ISBNs with kinds.
        volume: str | None - Volume.
        issue: str | None - Issue.
        page: str | None - Pages.
        article_number: str | None - Article number.
        part_number: str | None - Part number.
        component_number: str | None - Component number.
        edition_number: str | None - Edition number.
        special_numbering: str | None - Special numbering.
        journal_issue: JournalIssue | None - The issue.
        author: tuple[Contributor, ...] - Authors.
        editor: tuple[Contributor, ...] - Editors.
        chair: tuple[Contributor, ...] - Chairs.
        translator: tuple[Contributor, ...] - Translators.
        institution: tuple[Affiliation, ...] - Institutions.
        abstract: str | None - Abstract, JATS as sent.
        description: str | None - Description.
        language: str | None - Language.
        subject: tuple[str, ...] - Subjects.
        degree: tuple[str, ...] - Degrees of a dissertation.
        issued: PartialDate | None - Earliest publication date.
        published: PartialDate | None - Publication date.
        published_print: PartialDate | None - Print date.
        published_online: PartialDate | None - Online date.
        published_other: PartialDate | None - Other publication date.
        posted: PartialDate | None - Posting date.
        accepted: PartialDate | None - Acceptance date.
        approved: PartialDate | None - Approval date.
        content_created: PartialDate | None - When the content was created.
        content_updated: PartialDate | None - When it was updated.
        created: CrossrefTimestamp | None - First deposit.
        deposited: CrossrefTimestamp | None - Last deposit.
        indexed: CrossrefTimestamp | None - Last indexing.
        references_count: int | None - References deposited.
        reference_count: int | None - The same, older name.
        is_referenced_by_count: int | None - Citations in Crossref.
        reference: tuple[Reference, ...] - References.
        license: tuple[License, ...] - Licenses.
        link: tuple[Link, ...] - Full-text links.
        resource: Resources | None - URLs the DOI resolves to.
        funder: tuple[Funder, ...] - Funders.
        project: tuple[Project, ...] - Grant projects.
        clinical_trial_number: tuple[ClinicalTrial, ...] - Clinical trials.
        relation: Mapping[str, tuple[Relation, ...]] - Relations by type.
        update_to: tuple[Update, ...] - Works this one updates.
        updated_by: tuple[Update, ...] - Works that update this one.
        update_policy: str | None - Link to the update policy.
        assertion: tuple[Assertion, ...] - Crossmark assertions.
        content_domain: ContentDomain | None - Crossmark domains.
        event: Event | None - Event.
        review: Review | None - Peer review details.
        standards_body: StandardsBody | None - Body of a standard.
        free_to_read: FreeToRead | None - Free-to-read period.
        archive: tuple[str, ...] - Archives.
        alternative_id: tuple[str, ...] - Other identifiers.
        aliases: tuple[str, ...] - DOIs aliased to this one.
        proceedings_subject: str | None - Subject of proceedings.
        status: Mapping[str, object] | None - Status of a posted content, raw.
        score: float | None - Relevance score of a search.

    """

    doi: Doi = Field(alias="DOI")
    url: OptStr = Field(default=None, alias="URL")
    type: Annotated[
        WorkType | str | None,
        Field(union_mode="left_to_right"),
        lenient(None),
    ] = None
    subtype: OptStr = None
    title: CleanStrList = ()
    subtitle: CleanStrList = ()
    short_title: CleanStrList = Field(default=(), alias="short-title")
    original_title: CleanStrList = Field(default=(), alias="original-title")
    container_title: CleanStrList = Field(default=(), alias="container-title")
    short_container_title: CleanStrList = Field(
        default=(),
        alias="short-container-title",
    )
    group_title: OptStr = Field(default=None, alias="group-title")
    issue_title: CleanStrList = Field(default=(), alias="issue-title")
    publisher: OptStr = None
    publisher_location: OptStr = Field(default=None, alias="publisher-location")
    member: OptStr = None
    prefix: OptStr = None
    source: OptStr = None
    issn: IssnList = Field(default=(), alias="ISSN")
    issn_type: Annotated[tuple[IssnType, ...], lenient(())] = Field(
        default=(),
        alias="issn-type",
    )
    isbn: CleanStrList = Field(default=(), alias="ISBN")
    isbn_type: Annotated[tuple[IssnType, ...], lenient(())] = Field(
        default=(),
        alias="isbn-type",
    )
    volume: OptStr = None
    issue: OptStr = None
    page: OptStr = None
    article_number: OptStr = Field(default=None, alias="article-number")
    part_number: OptStr = Field(default=None, alias="part-number")
    component_number: OptStr = Field(default=None, alias="component-number")
    edition_number: OptStr = Field(default=None, alias="edition-number")
    special_numbering: OptStr = Field(default=None, alias="special-numbering")
    journal_issue: Annotated[JournalIssue | None, lenient(None)] = Field(
        default=None,
        alias="journal-issue",
    )
    author: Contributors = ()
    editor: Contributors = ()
    chair: Contributors = ()
    translator: Contributors = ()
    institution: Annotated[tuple[Affiliation, ...], lenient(())] = ()
    abstract: OptStr = None
    description: OptStr = None
    language: OptStr = None
    subject: CleanStrList = ()
    degree: CleanStrList = ()
    issued: Date = None
    published: Date = None
    published_print: Date = Field(default=None, alias="published-print")
    published_online: Date = Field(default=None, alias="published-online")
    published_other: Date = Field(default=None, alias="published-other")
    posted: Date = None
    accepted: Date = None
    approved: Date = None
    content_created: Date = Field(default=None, alias="content-created")
    content_updated: Date = Field(default=None, alias="content-updated")
    created: Stamp = None
    deposited: Stamp = None
    indexed: Stamp = None
    references_count: OptInt = Field(default=None, alias="references-count")
    reference_count: OptInt = Field(default=None, alias="reference-count")
    is_referenced_by_count: OptInt = Field(default=None, alias="is-referenced-by-count")
    reference: Annotated[tuple[Reference, ...], lenient(())] = ()
    license: Annotated[tuple[License, ...], lenient(())] = ()
    link: Annotated[tuple[Link, ...], lenient(())] = ()
    resource: Annotated[Resources | None, lenient(None)] = None
    funder: Annotated[tuple[Funder, ...], lenient(())] = ()
    project: Annotated[tuple[Project, ...], lenient(())] = ()
    clinical_trial_number: Annotated[tuple[ClinicalTrial, ...], lenient(())] = Field(
        default=(),
        alias="clinical-trial-number",
    )
    relation: Annotated[Mapping[str, tuple[Relation, ...]], lenient({})] = Field(
        default_factory=dict,
    )
    update_to: Annotated[tuple[Update, ...], lenient(())] = Field(
        default=(),
        alias="update-to",
    )
    updated_by: Annotated[tuple[Update, ...], lenient(())] = Field(
        default=(),
        alias="updated-by",
    )
    update_policy: OptStr = Field(default=None, alias="update-policy")
    assertion: Annotated[tuple[Assertion, ...], lenient(())] = ()
    content_domain: Annotated[ContentDomain | None, lenient(None)] = Field(
        default=None,
        alias="content-domain",
    )
    event: Annotated[Event | None, lenient(None)] = None
    review: Annotated[Review | None, lenient(None)] = None
    standards_body: Annotated[StandardsBody | None, lenient(None)] = Field(
        default=None,
        alias="standards-body",
    )
    free_to_read: Annotated[FreeToRead | None, lenient(None)] = Field(
        default=None,
        alias="free-to-read",
    )
    archive: CleanStrList = ()
    alternative_id: CleanStrList = Field(default=(), alias="alternative-id")
    aliases: CleanStrList = ()
    proceedings_subject: OptStr = Field(default=None, alias="proceedings-subject")
    status: Annotated[Mapping[str, object] | None, lenient(None)] = None
    score: OptFloat = None

    @property
    def main_title(self) -> str | None:
        """The first title.

        Returns:
            str | None - The title, or None.

        """
        return self.title[0] if self.title else None

    @property
    def journal_title(self) -> str | None:
        """The first container title: the journal of an article.

        Returns:
            str | None - The title, or None.

        """
        return self.container_title[0] if self.container_title else None

    @property
    def issn_print(self) -> str | None:
        """The print ISSN, normalized.

        Returns:
            str | None - The ISSN, or None.

        """
        return _issn_of_kind(self.issn_type, "print")

    @property
    def issn_electronic(self) -> str | None:
        """The electronic ISSN, normalized.

        Returns:
            str | None - The ISSN, or None.

        """
        return _issn_of_kind(self.issn_type, "electronic")

    @property
    def publication_date(self) -> PartialDate | None:
        """``issued``: Crossref's earliest of the publication dates.

        Returns:
            PartialDate | None - The date, or None.

        """
        return self.issued

    @property
    def year(self) -> int | None:
        """Year of ``publication_date``.

        Returns:
            int | None - The year, or None.

        """
        return None if self.issued is None else self.issued.year


def _issn_of_kind(entries: tuple[IssnType, ...], kind: str) -> str | None:
    for entry in entries:
        if entry.type == kind and entry.value is not None:
            try:
                return normalize_issn(entry.value)
            except CrossrefQueryError:
                return None
    return None
