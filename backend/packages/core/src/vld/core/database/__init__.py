"""Database kit shared by the domains: engine, metadata, mixins, unit of work."""

from __future__ import annotations

from ._engine import create_engine, create_session_factory
from ._enums import PostgresEnum
from ._integrity import is_foreign_key_violation, is_unique_violation
from ._metadata import NAMING_CONVENTION, make_metadata
from .mixins import BigIntPkMixin, CreatedAtMixin, TimestampMixin, UUIDPkMixin
from .uow import SqlAlchemyUnitOfWork, UnitOfWork

__all__ = (
    "NAMING_CONVENTION",
    "BigIntPkMixin",
    "CreatedAtMixin",
    "PostgresEnum",
    "SqlAlchemyUnitOfWork",
    "TimestampMixin",
    "UUIDPkMixin",
    "UnitOfWork",
    "create_engine",
    "create_session_factory",
    "is_foreign_key_violation",
    "is_unique_violation",
    "make_metadata",
)
