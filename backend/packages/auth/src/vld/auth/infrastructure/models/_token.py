"""ORM model of a one-time token."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
from datetime import (
    datetime,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from vld.auth.domain import TokenPurpose
from vld.core.database import BigIntPkMixin, CreatedAtMixin, PostgresEnum

from ._base import METADATA, USERS_ID_FK, AuthBase
from ._tables import TOKEN_PURPOSE, VERIFICATION_TOKENS


class VerificationTokenModel(BigIntPkMixin, CreatedAtMixin, AuthBase):
    """Row of a one-time token."""

    __tablename__: str = VERIFICATION_TOKENS

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(USERS_ID_FK, ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    purpose: Mapped[TokenPurpose] = mapped_column(
        PostgresEnum(TokenPurpose, TOKEN_PURPOSE, metadata=METADATA)(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
