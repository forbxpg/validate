"""Миксины временных меток."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 -- см. комментарий ниже

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Метки создания и изменения — для изменяемых сущностей.

    Attributes:
        created_at: datetime - Когда создано.
        updated_at: datetime - Когда изменено в последний раз.

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
    """Только метка создания — для append-only, где строки не меняются.

    Attributes:
        created_at: datetime - Когда создано.

    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
