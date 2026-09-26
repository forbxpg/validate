"""Enumerations of the journals domain."""

from __future__ import annotations

from enum import StrEnum


class Channel(StrEnum):
    """Where an import or a publication came from."""

    CLI = "cli"


class DocumentSource(StrEnum):
    """How a document of the list reached us."""

    DOWNLOAD = "download"
    FILE = "file"


class IssnSource(StrEnum):
    """Who gave an ISSN to a journal: an import, or a moderator's choice."""

    IMPORT = "import"
    MODERATOR = "moderator"


class PublicationKind(StrEnum):
    """What moved the pointer to the current snapshot."""

    PUBLISH = "publish"
    ROLLBACK = "rollback"
