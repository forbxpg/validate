"""ORM model of an account."""

from __future__ import annotations

from datetime import (
    datetime,  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from sqlalchemy import CheckConstraint, DateTime, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column

from vld.auth.domain import Role
from vld.core.database import PostgresEnum, TimestampMixin, UUIDPkMixin

from ._base import METADATA, AuthBase
from ._tables import EMAIL_LOWER_CASE_CONSTRAINT, ROLE, USERS


class UserModel(UUIDPkMixin, TimestampMixin, AuthBase):
    """Row of an account."""

    __tablename__: str = USERS
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            "email = lower(email)",
            name=EMAIL_LOWER_CASE_CONSTRAINT,
        ),
    )

    email: Mapped[str] = mapped_column(Text, unique=True, comment="The email address.")
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="The moment the email was verified.",
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        comment="The hash of the password.",
    )
    role: Mapped[Role] = mapped_column(
        PostgresEnum(Role, ROLE, metadata=METADATA)(),
        comment="The role of the user.",
    )
    is_admin: Mapped[bool] = mapped_column(
        server_default=false(),
        comment="Whether the user is an administrator.",
    )
    is_active: Mapped[bool] = mapped_column(
        server_default=true(),
        comment="Whether the user is active.",
    )
    tokens_invalidated_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="The moment the tokens were invalidated.",
    )
    first_name_ru: Mapped[str | None] = mapped_column(
        Text,
        comment="The first name in Russian.",
    )
    last_name_ru: Mapped[str | None] = mapped_column(
        Text,
        comment="The last name in Russian.",
    )
    first_name_en: Mapped[str | None] = mapped_column(
        Text,
        comment="The first name in English.",
    )
    last_name_en: Mapped[str | None] = mapped_column(
        Text,
        comment="The last name in English.",
    )
    group_number: Mapped[str | None] = mapped_column(
        Text,
        comment="The group number.",
    )
    institution_name: Mapped[str | None] = mapped_column(
        Text,
        comment="The name of the institution.",
    )
