"""Values Crossref accepts on the works routes, as it listed them on 2026-09-26."""

from __future__ import annotations

from enum import StrEnum


class WorkType(StrEnum):
    """Types of works, the ids of ``/types``."""

    BOOK = "book"
    BOOK_CHAPTER = "book-chapter"
    BOOK_PART = "book-part"
    BOOK_SECTION = "book-section"
    BOOK_SERIES = "book-series"
    BOOK_SET = "book-set"
    BOOK_TRACK = "book-track"
    COMPONENT = "component"
    DATABASE = "database"
    DATASET = "dataset"
    DISSERTATION = "dissertation"
    EDITED_BOOK = "edited-book"
    GRANT = "grant"
    JOURNAL = "journal"
    JOURNAL_ARTICLE = "journal-article"
    JOURNAL_ISSUE = "journal-issue"
    JOURNAL_VOLUME = "journal-volume"
    MONOGRAPH = "monograph"
    OTHER = "other"
    PEER_REVIEW = "peer-review"
    POSTED_CONTENT = "posted-content"
    PROCEEDINGS = "proceedings"
    PROCEEDINGS_ARTICLE = "proceedings-article"
    PROCEEDINGS_SERIES = "proceedings-series"
    REFERENCE_BOOK = "reference-book"
    REFERENCE_ENTRY = "reference-entry"
    REPORT = "report"
    REPORT_COMPONENT = "report-component"
    REPORT_SERIES = "report-series"
    STANDARD = "standard"


class WorksSort(StrEnum):
    """Fields works can be sorted by."""

    CREATED = "created"
    DEPOSITED = "deposited"
    INDEXED = "indexed"
    IS_REFERENCED_BY_COUNT = "is-referenced-by-count"
    ISSUED = "issued"
    PUBLISHED = "published"
    PUBLISHED_ONLINE = "published-online"
    PUBLISHED_PRINT = "published-print"
    REFERENCES_COUNT = "references-count"
    RELEVANCE = "relevance"
    SCORE = "score"
    UPDATED = "updated"


class Order(StrEnum):
    """Direction of a sort; Crossref sorts descending by default."""

    ASC = "asc"
    DESC = "desc"


class WorkField(StrEnum):
    """Fields ``select`` can return."""

    DOI = "DOI"
    ISBN = "ISBN"
    ISSN = "ISSN"
    URL = "URL"
    ABSTRACT = "abstract"
    ACCEPTED = "accepted"
    ALTERNATIVE_ID = "alternative-id"
    APPROVED = "approved"
    ARCHIVE = "archive"
    ARTICLE_NUMBER = "article-number"
    ASSERTION = "assertion"
    AUTHOR = "author"
    CHAIR = "chair"
    CLINICAL_TRIAL_NUMBER = "clinical-trial-number"
    CONTAINER_TITLE = "container-title"
    CONTENT_CREATED = "content-created"
    CONTENT_DOMAIN = "content-domain"
    CONTRIBUTOR = "contributor"
    CREATED = "created"
    DEGREE = "degree"
    DEPOSITED = "deposited"
    EDITOR = "editor"
    EVENT = "event"
    FUNDER = "funder"
    GROUP_TITLE = "group-title"
    INDEXED = "indexed"
    IS_REFERENCED_BY_COUNT = "is-referenced-by-count"
    ISSN_TYPE = "issn-type"
    ISSUE = "issue"
    ISSUED = "issued"
    LICENSE = "license"
    LINK = "link"
    MEMBER = "member"
    ORIGINAL_TITLE = "original-title"
    PAGE = "page"
    POSTED = "posted"
    PREFIX = "prefix"
    PUBLISHED = "published"
    PUBLISHED_ONLINE = "published-online"
    PUBLISHED_PRINT = "published-print"
    PUBLISHER = "publisher"
    PUBLISHER_LOCATION = "publisher-location"
    REFERENCE = "reference"
    REFERENCES_COUNT = "references-count"
    RELATION = "relation"
    RESOURCE = "resource"
    SCORE = "score"
    SHORT_CONTAINER_TITLE = "short-container-title"
    SHORT_TITLE = "short-title"
    STANDARDS_BODY = "standards-body"
    SUBJECT = "subject"
    SUBTITLE = "subtitle"
    TITLE = "title"
    TRANSLATOR = "translator"
    TYPE = "type"
    UPDATE_POLICY = "update-policy"
    UPDATE_TO = "update-to"
    UPDATED_BY = "updated-by"
    VOLUME = "volume"


class WorkFacet(StrEnum):
    """Facets of works (Crossref also lists ``*``, which returns an empty facet)."""

    AFFILIATION = "affiliation"
    ARCHIVE = "archive"
    ASSERTION = "assertion"
    ASSERTION_GROUP = "assertion-group"
    CATEGORY_NAME = "category-name"
    CONTAINER_TITLE = "container-title"
    FUNDER_DOI = "funder-doi"
    FUNDER_NAME = "funder-name"
    ISSN = "issn"
    JOURNAL_ISSUE = "journal-issue"
    JOURNAL_VOLUME = "journal-volume"
    LICENSE = "license"
    LINK_APPLICATION = "link-application"
    ORCID = "orcid"
    PUBLISHED = "published"
    PUBLISHER_NAME = "publisher-name"
    RELATION_TYPE = "relation-type"
    ROR_ID = "ror-id"
    SOURCE = "source"
    TYPE_NAME = "type-name"
    UPDATE_TYPE = "update-type"


class LicenseVersion(StrEnum):
    """Versions a license applies to."""

    AM = "am"
    STM_ASF = "stm-asf"
    TDM = "tdm"
    VOR = "vor"


class FullTextApplication(StrEnum):
    """What a full-text link is meant for."""

    SIMILARITY_CHECKING = "similarity-checking"
    TEXT_MINING = "text-mining"
    UNSPECIFIED = "unspecified"


class FunderDoiAssertedBy(StrEnum):
    """Who asserted the DOI of a funder."""

    CROSSREF = "crossref"
    PUBLISHER = "publisher"
