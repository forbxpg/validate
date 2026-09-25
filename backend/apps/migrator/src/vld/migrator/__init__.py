"""Database migrator: one Alembic chain for every domain, run safely before a deploy."""

from __future__ import annotations

from ._cli import main
from ._connection import create_migration_engine
from ._errors import (
    BackupError,
    MigrationLockBusyError,
    MigratorError,
    PreflightError,
    SchemaDriftError,
)
from ._layout import (
    DOMAIN_METADATA,
    VERSION_SCHEMA,
    managed_schemas,
    target_metadata,
)

__all__ = (
    "DOMAIN_METADATA",
    "VERSION_SCHEMA",
    "BackupError",
    "MigrationLockBusyError",
    "MigratorError",
    "PreflightError",
    "SchemaDriftError",
    "create_migration_engine",
    "main",
    "managed_schemas",
    "target_metadata",
)
