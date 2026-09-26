"""The identity of a journal and whose ISSN is whose, shared by every registry."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
from datetime import (
    datetime,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from vld.core.database import UUIDPkMixin
from vld.journals.domain import (
    IssnSource,  # ruff: ignore[typing-only-first-party-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from ._base import JournalsBase, fk
from ._enums import ISSN_SOURCE_TYPE
from ._tables import ISSN_PATTERN, JOURNAL, JOURNAL_ISSN


class JournalModel(UUIDPkMixin, JournalsBase):
    """A journal: identity only; its title belongs to each edition that lists it."""

    __tablename__: str = JOURNAL

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="When the journal was first seen.",
    )


class JournalIssnModel(JournalsBase):
    """Whose an ISSN is: one journal per ISSN, chosen by an import or a moderator."""

    __tablename__: str = JOURNAL_ISSN
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(f"issn ~ '{ISSN_PATTERN}'", name="issn_format"),
    )

    issn: Mapped[str] = mapped_column(Text, primary_key=True, comment="NNNN-NNNC.")
    journal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(JOURNAL)),
        index=True,
        comment="The journal the ISSN belongs to.",
    )
    source: Mapped[IssnSource] = mapped_column(
        ISSN_SOURCE_TYPE,
        comment="An import gave it, or a moderator chose it.",
    )
    assigned_by: Mapped[str] = mapped_column(Text, comment="Who gave it: user@host.")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="When it was given.",
    )
