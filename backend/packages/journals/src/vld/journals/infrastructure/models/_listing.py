"""A journal in an edition: what the list prints about it, row by row, never changed."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
from datetime import (
    date,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from vld.core.database import BigIntPkMixin

from ._base import JournalsBase, fk
from ._tables import (
    ISSN_PATTERN,
    JOURNAL,
    LISTING_JOURNAL,
    LISTING_NUMBER,
    SPECIALITY,
    VAK_FORMER_ISSN,
    VAK_FORMER_TITLE,
    VAK_GROUP,
    VAK_GROUP_SPECIALITY,
    VAK_LISTING,
    VAK_LISTING_ISSN,
    VAK_SNAPSHOT,
)

_POSITION = "position > 0"


class VakListingModel(BigIntPkMixin, JournalsBase):
    """One numbered entry of an edition, tied to the journal it is."""

    __tablename__: str = VAK_LISTING
    __table_args__: tuple[CheckConstraint | UniqueConstraint | Index, ...] = (
        CheckConstraint("number > 0", name="number_positive"),
        CheckConstraint("0 < first_page AND first_page <= last_page", name="pages"),
        UniqueConstraint("snapshot_id", "number", name=LISTING_NUMBER),
        UniqueConstraint("snapshot_id", "journal_id", name=LISTING_JOURNAL),
        Index(None, "journal_id", "snapshot_id"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(VAK_SNAPSHOT)),
        comment="The edition.",
    )
    journal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(JOURNAL)),
        comment="The journal the entry is.",
    )
    number: Mapped[int] = mapped_column(Integer, comment="«№ п/п».")
    first_page: Mapped[int] = mapped_column(Integer, comment="First page of the entry.")
    last_page: Mapped[int] = mapped_column(Integer, comment="Last page of the entry.")
    title_printed: Mapped[str] = mapped_column(Text, comment="The title cell verbatim.")
    title_main: Mapped[str] = mapped_column(Text, comment="The title without brackets.")
    title_translation: Mapped[str | None] = mapped_column(
        Text,
        comment="The translation into Russian.",
    )
    issn_printed: Mapped[str] = mapped_column(Text, comment="The ISSN cell verbatim.")


class VakListingIssnModel(JournalsBase):
    """An ISSN as the entry prints it; whose it is, `journal_issn` says."""

    __tablename__: str = VAK_LISTING_ISSN
    __table_args__: tuple[CheckConstraint | Index, ...] = (
        CheckConstraint(_POSITION, name="position_positive"),
        CheckConstraint(f"issn ~ '{ISSN_PATTERN}'", name="issn_format"),
        Index(None, "issn"),
    )

    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(fk(VAK_LISTING)),
        primary_key=True,
        comment="The entry.",
    )
    position: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        comment="Place in the cell, from 1.",
    )
    issn: Mapped[str] = mapped_column(Text, comment="NNNN-NNNC as printed.")


class VakFormerTitleModel(BigIntPkMixin, JournalsBase):
    """A title the entry had before a rename, as the edition prints it."""

    __tablename__: str = VAK_FORMER_TITLE
    __table_args__: tuple[CheckConstraint | UniqueConstraint, ...] = (
        CheckConstraint(_POSITION, name="position_positive"),
        UniqueConstraint("listing_id", "position"),
    )

    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(fk(VAK_LISTING)),
        comment="The entry.",
    )
    position: Mapped[int] = mapped_column(SmallInteger, comment="Place in the title.")
    title: Mapped[str] = mapped_column(Text, comment="The former title.")
    until: Mapped[date | None] = mapped_column(Date, comment="Used until this date.")


class VakFormerIssnModel(JournalsBase):
    """An ISSN of a former title: the link across a change of ISSN."""

    __tablename__: str = VAK_FORMER_ISSN
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(_POSITION, name="position_positive"),
        CheckConstraint(f"issn ~ '{ISSN_PATTERN}'", name="issn_format"),
    )

    former_title_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(fk(VAK_FORMER_TITLE)),
        primary_key=True,
        comment="The former title.",
    )
    position: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        comment="Place in the bracket, from 1.",
    )
    issn: Mapped[str] = mapped_column(Text, comment="NNNN-NNNC as printed.")


class VakGroupModel(BigIntPkMixin, JournalsBase):
    """Specialities of an entry that share one date cell."""

    __tablename__: str = VAK_GROUP
    __table_args__: tuple[CheckConstraint | UniqueConstraint, ...] = (
        CheckConstraint(_POSITION, name="position_positive"),
        UniqueConstraint("listing_id", "position"),
    )

    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(fk(VAK_LISTING)),
        comment="The entry.",
    )
    position: Mapped[int] = mapped_column(SmallInteger, comment="Place in the entry.")
    dates_printed: Mapped[str] = mapped_column(Text, comment="The date cell verbatim.")
    included: Mapped[date | None] = mapped_column(Date, comment="The «с» date.")
    excluded: Mapped[date | None] = mapped_column(Date, comment="The «по» date.")


class VakGroupSpecialityModel(JournalsBase):
    """A speciality of a group, with its name as this row prints it."""

    __tablename__: str = VAK_GROUP_SPECIALITY
    __table_args__: tuple[CheckConstraint | Index, ...] = (
        CheckConstraint(_POSITION, name="position_positive"),
        Index(None, "speciality_id", "group_id"),
    )

    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(fk(VAK_GROUP)),
        primary_key=True,
        comment="The group.",
    )
    position: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        comment="Place in the group, from 1.",
    )
    speciality_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(SPECIALITY)),
        comment="The speciality.",
    )
    name_printed: Mapped[str] = mapped_column(Text, comment="Its name in this row.")
    printed: Mapped[str] = mapped_column(Text, comment="The speciality verbatim.")
