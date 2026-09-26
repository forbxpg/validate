"""A snapshot: one edition as one parser version read it, with that reading."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
from datetime import (
    date,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
    datetime,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from vld.core.database import BigIntPkMixin, UUIDPkMixin
from vld.journals.domain import (
    Channel,  # ruff: ignore[typing-only-first-party-import] -- SQLAlchemy reads Mapped[...] at runtime
)
from vld.vak.models import (
    WarningCode,  # ruff: ignore[typing-only-first-party-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from ._base import JournalsBase, fk
from ._enums import CHANNEL_TYPE, VAK_WARNING_CODE_TYPE
from ._tables import (
    SNAPSHOT_IDENTITY,
    VAK_DOCUMENT,
    VAK_PARSE,
    VAK_PARSE_WARNING,
    VAK_SNAPSHOT,
)


class VakSnapshotModel(UUIDPkMixin, JournalsBase):
    """An edition as read: a draft until a publication points at it; never changed."""

    __tablename__: str = VAK_SNAPSHOT
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("document_id", "parser_version", name=SNAPSHOT_IDENTITY),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(VAK_DOCUMENT)),
        comment="The document read.",
    )
    parser_version: Mapped[str] = mapped_column(Text, comment="Version of vld-vak.")
    edition_date: Mapped[date] = mapped_column(Date, comment="«По состоянию на».")
    channel: Mapped[Channel] = mapped_column(
        CHANNEL_TYPE,
        comment="Where it came from.",
    )
    operator: Mapped[str] = mapped_column(Text, comment="Who imported it: user@host.")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="When it was imported.",
    )


class VakParseModel(JournalsBase):
    """The parse result of a snapshot, the JSON of vld-vak compressed with gzip."""

    __tablename__: str = VAK_PARSE

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(VAK_SNAPSHOT)),
        primary_key=True,
        comment="The snapshot.",
    )
    format_version: Mapped[int] = mapped_column(
        SmallInteger,
        comment="format_version of the JSON.",
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, comment="gzip of the JSON.")


class VakParseWarningModel(BigIntPkMixin, JournalsBase):
    """A warning of the parse, a copy of the JSON's for filtering in SQL."""

    __tablename__: str = VAK_PARSE_WARNING
    __table_args__: tuple[Index, ...] = (Index(None, "snapshot_id", "code"),)

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(VAK_SNAPSHOT)),
        comment="The snapshot.",
    )
    code: Mapped[WarningCode] = mapped_column(
        VAK_WARNING_CODE_TYPE,
        comment="What it is about.",
    )
    page: Mapped[int | None] = mapped_column(Integer, comment="Page of the document.")
    journal_number: Mapped[int | None] = mapped_column(
        Integer,
        comment="Number of the journal it is about.",
    )
    printed: Mapped[str] = mapped_column(Text, comment="The text concerned.")
    message: Mapped[str] = mapped_column(Text, comment="Explanation.")
