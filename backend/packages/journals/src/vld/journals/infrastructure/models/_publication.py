"""Which snapshot is current, and every move of that pointer."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
from datetime import (
    datetime,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from vld.core.database import BigIntPkMixin
from vld.journals.domain import (
    Channel,  # ruff: ignore[typing-only-first-party-import] -- SQLAlchemy reads Mapped[...] at runtime
    PublicationKind,  # ruff: ignore[typing-only-first-party-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from ._base import JournalsBase, fk
from ._enums import CHANNEL_TYPE, PUBLICATION_KIND_TYPE
from ._tables import (
    CURRENT_SINGLETON,
    PUBLICATION_REASON,
    VAK_CURRENT,
    VAK_PUBLICATION,
    VAK_SNAPSHOT,
)


class VakCurrentModel(JournalsBase):
    """The pointer to the current snapshot: one row once something is published."""

    __tablename__: str = VAK_CURRENT
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("singleton", name=CURRENT_SINGLETON),
    )

    singleton: Mapped[bool] = mapped_column(
        Boolean,
        primary_key=True,
        server_default=true(),
        comment="Always true: the key that allows one row.",
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(VAK_SNAPSHOT)),
        comment="The current snapshot.",
    )


class VakPublicationModel(BigIntPkMixin, JournalsBase):
    """A move of the pointer: a publication or a rollback; the log of what we knew."""

    __tablename__: str = VAK_PUBLICATION
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            "(kind = 'publish' AND NOT forced) OR reason IS NOT NULL",
            name=PUBLICATION_REASON,
        ),
        CheckConstraint(
            "from_snapshot_id IS DISTINCT FROM to_snapshot_id",
            name="moves",
        ),
    )

    kind: Mapped[PublicationKind] = mapped_column(
        PUBLICATION_KIND_TYPE,
        comment="Publication or rollback.",
    )
    from_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(fk(VAK_SNAPSHOT)),
        comment="The snapshot current before; none for the first publication.",
    )
    to_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(fk(VAK_SNAPSHOT)),
        index=True,
        comment="The snapshot current after.",
    )
    forced: Mapped[bool] = mapped_column(
        Boolean,
        comment="Published over tripped quality checks.",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        comment="Why: required for a rollback and a forced publication.",
    )
    channel: Mapped[Channel] = mapped_column(
        CHANNEL_TYPE,
        comment="Where it came from.",
    )
    operator: Mapped[str] = mapped_column(Text, comment="Who: user@host.")
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="When the pointer moved.",
    )
