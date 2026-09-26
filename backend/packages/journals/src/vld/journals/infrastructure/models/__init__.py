"""ORM models of the journals schema, one module per entity."""

from __future__ import annotations

from ._base import METADATA, JournalsBase
from ._document import VakDocumentFileModel, VakDocumentModel
from ._journal import JournalIssnModel, JournalModel
from ._listing import (
    VakFormerIssnModel,
    VakFormerTitleModel,
    VakGroupModel,
    VakGroupSpecialityModel,
    VakListingIssnModel,
    VakListingModel,
)
from ._publication import VakCurrentModel, VakPublicationModel
from ._snapshot import VakParseModel, VakParseWarningModel, VakSnapshotModel
from ._speciality import SpecialityModel
from ._tables import (
    CHANNEL,
    DOCUMENT_SOURCE,
    ISSN_SOURCE,
    JOURNAL,
    JOURNAL_ISSN,
    PUBLICATION_KIND,
    SCHEMA,
    SCIENCE_BRANCH,
    SPECIALITY,
    VAK_CURRENT,
    VAK_DOCUMENT,
    VAK_DOCUMENT_FILE,
    VAK_FORMER_ISSN,
    VAK_FORMER_TITLE,
    VAK_GROUP,
    VAK_GROUP_SPECIALITY,
    VAK_LISTING,
    VAK_LISTING_ISSN,
    VAK_PARSE,
    VAK_PARSE_WARNING,
    VAK_PUBLICATION,
    VAK_SNAPSHOT,
    VAK_WARNING_CODE,
)

__all__ = (
    "CHANNEL",
    "DOCUMENT_SOURCE",
    "ISSN_SOURCE",
    "JOURNAL",
    "JOURNAL_ISSN",
    "METADATA",
    "PUBLICATION_KIND",
    "SCHEMA",
    "SCIENCE_BRANCH",
    "SPECIALITY",
    "VAK_CURRENT",
    "VAK_DOCUMENT",
    "VAK_DOCUMENT_FILE",
    "VAK_FORMER_ISSN",
    "VAK_FORMER_TITLE",
    "VAK_GROUP",
    "VAK_GROUP_SPECIALITY",
    "VAK_LISTING",
    "VAK_LISTING_ISSN",
    "VAK_PARSE",
    "VAK_PARSE_WARNING",
    "VAK_PUBLICATION",
    "VAK_SNAPSHOT",
    "VAK_WARNING_CODE",
    "JournalIssnModel",
    "JournalModel",
    "JournalsBase",
    "SpecialityModel",
    "VakCurrentModel",
    "VakDocumentFileModel",
    "VakDocumentModel",
    "VakFormerIssnModel",
    "VakFormerTitleModel",
    "VakGroupModel",
    "VakGroupSpecialityModel",
    "VakListingIssnModel",
    "VakListingModel",
    "VakParseModel",
    "VakParseWarningModel",
    "VakPublicationModel",
    "VakSnapshotModel",
)
