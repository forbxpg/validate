"""ORM model of a row of the transactional outbox."""

from __future__ import annotations

from datetime import datetime  # ruff: ignore[typing-only-standard-library-import]
from enum import StrEnum

from sqlalchemy import DateTime, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vld.core.database import BigIntPkMixin, PostgresEnum

from ._base import METADATA, AuthBase
from ._tables import OUTBOX, OUTBOX_STATUS


class OutboxStatus(StrEnum):
    """Where a row is in the relay.

    Attributes:
        PENDING: str - Waits for the relay.
        SENDING: str - Claimed by a worker right now.
        SENT: str - Handled; `published_at` is set.
        FAILED: str - Cannot be handled: poison, or the attempts ran out.

    """

    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


PENDING_PREDICATE = f"status = '{OutboxStatus.PENDING.value}'"
CLAIMABLE_PREDICATE = (
    f"{PENDING_PREDICATE} AND (next_attempt_at IS NULL OR next_attempt_at <= now())"
)


class OutboxModel(BigIntPkMixin, AuthBase):
    """A domain event waiting for the relay."""

    __tablename__: str = OUTBOX
    __table_args__: tuple[Index, ...] = (
        Index(
            f"ix_{OUTBOX}_pending",
            "id",
            postgresql_where=text(PENDING_PREDICATE),
        ),
    )

    event_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The name of the event.",
    )
    payload: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        comment="The payload of the event.",
    )
    status: Mapped[OutboxStatus] = mapped_column(
        PostgresEnum(
            OutboxStatus,
            OUTBOX_STATUS,
            metadata=METADATA,
        )(),
        server_default=text(f"'{OutboxStatus.PENDING.value}'"),
        comment="The status of the event.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="The moment the event was created.",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="The moment the event was published.",
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="The moment the event was claimed.",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        comment="The number of attempts to publish the event.",
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="The moment the next attempt to publish the event will be made.",
    )
