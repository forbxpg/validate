"""Timestamp mixins."""

from __future__ import annotations

from datetime import datetime  # ruff: ignore[typing-only-standard-library-import]

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Creation and update timestamps for mutable entities.

    Attributes:
        created_at: datetime - When the row was created.
        updated_at: datetime - When the row was last changed.

    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CreatedAtMixin:
    """Creation timestamp only, for append-only rows that never change.

    Attributes:
        created_at: datetime - When the row was created.

    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
