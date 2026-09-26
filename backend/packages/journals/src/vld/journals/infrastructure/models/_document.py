"""A document of the VAK list: every file we saw, and the latest one itself."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
from datetime import (
    datetime,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from vld.core.database import UUIDPkMixin
from vld.journals.domain import (
    DocumentSource,  # ruff: ignore[typing-only-first-party-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from ._base import JournalsBase, fk
from ._enums import DOCUMENT_SOURCE_TYPE
from ._tables import VAK_DOCUMENT, VAK_DOCUMENT_FILE

_SHA256_BYTES = 32


class VakDocumentModel(UUIDPkMixin, JournalsBase):
    """A PDF of the list we imported: kept for good, its bytes only while latest."""

    __tablename__: str = VAK_DOCUMENT
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            f"octet_length(sha256) = {_SHA256_BYTES}",
            name="sha256_length",
        ),
        CheckConstraint("size > 0", name="size_positive"),
        CheckConstraint("url IS NOT NULL OR file_name IS NOT NULL", name="has_origin"),
    )

    sha256: Mapped[bytes] = mapped_column(
        LargeBinary,
        unique=True,
        comment="SHA-256 of the file: its identity.",
    )
    size: Mapped[int] = mapped_column(BigInteger, comment="Size in bytes.")
    source: Mapped[DocumentSource] = mapped_column(
        DOCUMENT_SOURCE_TYPE,
        comment="Downloaded from the site of VAK, or given as a file.",
    )
    url: Mapped[str | None] = mapped_column(Text, comment="Where it was downloaded.")
    file_name: Mapped[str | None] = mapped_column(
        Text,
        comment="The file it came from.",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="When it was fetched or read.",
    )


class VakDocumentFileModel(JournalsBase):
    """The bytes of the latest document; the row of the one before is deleted."""

    __tablename__: str = VAK_DOCUMENT_FILE

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(VAK_DOCUMENT)),
        primary_key=True,
        comment="The document.",
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, comment="The PDF.")
