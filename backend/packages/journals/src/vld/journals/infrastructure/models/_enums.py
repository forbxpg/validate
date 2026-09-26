"""The PostgreSQL enums of the schema, bound to its metadata."""

from __future__ import annotations

from vld.core.database import PostgresEnum
from vld.journals.domain import Channel, DocumentSource, IssnSource, PublicationKind
from vld.vak.models import ScienceBranch, WarningCode

from ._base import METADATA
from ._tables import (
    CHANNEL,
    DOCUMENT_SOURCE,
    ISSN_SOURCE,
    PUBLICATION_KIND,
    SCIENCE_BRANCH,
    VAK_WARNING_CODE,
)

SCIENCE_BRANCH_TYPE = PostgresEnum(ScienceBranch, SCIENCE_BRANCH, metadata=METADATA)()
VAK_WARNING_CODE_TYPE = PostgresEnum(WarningCode, VAK_WARNING_CODE, metadata=METADATA)()
CHANNEL_TYPE = PostgresEnum(Channel, CHANNEL, metadata=METADATA)()
DOCUMENT_SOURCE_TYPE = PostgresEnum(
    DocumentSource,
    DOCUMENT_SOURCE,
    metadata=METADATA,
)()
ISSN_SOURCE_TYPE = PostgresEnum(IssnSource, ISSN_SOURCE, metadata=METADATA)()
PUBLICATION_KIND_TYPE = PostgresEnum(
    PublicationKind,
    PUBLICATION_KIND,
    metadata=METADATA,
)()
