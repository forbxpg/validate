from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy.orm import DeclarativeBase, configure_mappers

from vld.core.database import make_metadata
from vld.core.database.mixins import (
    BigIntPkMixin,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPkMixin,
)

if TYPE_CHECKING:
    from sqlalchemy import MetaData


def test_mixins_survive_mapper_configuration() -> None:
    probe_metadata = make_metadata("mixin_probe")

    class Base(DeclarativeBase):
        metadata: ClassVar[MetaData] = probe_metadata

    class Mutable(UUIDPkMixin, TimestampMixin, Base):
        __tablename__: str = "mutable"

    class AppendOnly(BigIntPkMixin, CreatedAtMixin, Base):
        __tablename__: str = "append_only"

    configure_mappers()
    assert Mutable.__mapper__.columns["updated_at"] is not None
    assert AppendOnly.__mapper__.columns["created_at"] is not None
