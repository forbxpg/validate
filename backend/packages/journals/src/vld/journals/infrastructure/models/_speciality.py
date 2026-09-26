"""The identity of a scientific speciality: its code in a branch of science."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vld.core.database import UUIDPkMixin
from vld.vak.models import (
    ScienceBranch,  # ruff: ignore[typing-only-first-party-import] -- SQLAlchemy reads Mapped[...] at runtime
)

from ._base import JournalsBase
from ._enums import SCIENCE_BRANCH_TYPE
from ._tables import SPECIALITY, SPECIALITY_CODE_PATTERN, SPECIALITY_IDENTITY


class SpecialityModel(UUIDPkMixin, JournalsBase):
    """A speciality: code and branch; its name is printed in each fact.

    A speciality whose branch could not be read has no branch: one such row per
    code, kept out of branch queries and never out of an edition.
    """

    __tablename__: str = SPECIALITY
    __table_args__: tuple[CheckConstraint | UniqueConstraint, ...] = (
        CheckConstraint(f"code ~ '{SPECIALITY_CODE_PATTERN}'", name="code_format"),
        UniqueConstraint(
            "code",
            "branch",
            name=SPECIALITY_IDENTITY,
            postgresql_nulls_not_distinct=True,
        ),
    )

    code: Mapped[str] = mapped_column(Text, comment="5.9.5 or 10.02.01.")
    branch: Mapped[ScienceBranch | None] = mapped_column(
        SCIENCE_BRANCH_TYPE,
        comment="The branch of science; none when it could not be read.",
    )
