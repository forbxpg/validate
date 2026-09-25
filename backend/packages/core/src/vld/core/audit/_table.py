"""Audit log table."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from vld.core.database import make_metadata

from ._tables import AUDIT_LOG_TABLE_NAME, AUDIT_SCHEMA_NAME

METADATA: MetaData = make_metadata(AUDIT_SCHEMA_NAME)


AUDIT_LOG_TABLE = Table(
    AUDIT_LOG_TABLE_NAME,
    METADATA,
    Column(
        "id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Record number",
    ),
    Column(
        "occurred_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When it happened",
    ),
    Column(
        "actor_id",
        UUID(as_uuid=True),
        nullable=True,
        comment="Who did it",
    ),
    Column(
        "action",
        Text,
        nullable=False,
        comment="What happened",
    ),
    Column(
        "target_id",
        UUID(as_uuid=True),
        nullable=True,
        comment="Over whom",
    ),
    Column(
        "payload",
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Useful record payload",
    ),
)
