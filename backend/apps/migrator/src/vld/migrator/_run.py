"""The two runs of the migrator: upgrade and check."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from alembic.script import ScriptDirectory

from ._backup import client_major, prune_backups, server_major, take_backup
from ._errors import BackupError
from ._layout import managed_schemas, target_metadata
from ._postflight import check_no_drift
from ._preflight import (
    check_no_invalid_indexes,
    check_not_ahead,
    check_single_head,
    current_revision,
)
from ._upgrade import upgrade_to_head

if TYPE_CHECKING:
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import URL, Connection

    from ._settings import MigratorSettings

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


def run_check(connection: Connection, config: Config) -> str | None:
    """Check the scripts and the database without changing anything.

    Args:
        connection: Connection - The run's connection.
        config: Config - Alembic configuration.

    Returns:
        str | None - The database revision.

    """
    scripts = ScriptDirectory.from_config(config)
    metadata = target_metadata(config)
    schemas = managed_schemas(metadata)
    check_single_head(scripts)
    revision = current_revision(connection)
    check_not_ahead(scripts, revision)
    check_no_invalid_indexes(connection, schemas)
    if revision == scripts.get_current_head():
        check_no_drift(connection, metadata, schemas)
    return revision


def run_upgrade(
    connection: Connection,
    config: Config,
    settings: MigratorSettings,
    url: URL,
    *,
    backup: bool,
) -> None:
    """Check, back up, upgrade to head and verify the result.

    Args:
        connection: Connection - The run's connection, holding the lock.
        config: Config - Alembic configuration.
        settings: MigratorSettings - Backup and executable settings.
        url: URL - The database, for `pg_dump`.
        backup: bool - Take a dump before pending revisions.

    Raises:
        BackupError: If a backup is required but not configured.

    """
    if backup and settings.backup_dir is None:
        msg = "MIGRATOR_BACKUP_DIR is not set; pass --no-backup to run without one"
        raise BackupError(msg)
    scripts = ScriptDirectory.from_config(config)
    metadata = target_metadata(config)
    schemas = managed_schemas(metadata)
    check_single_head(scripts)
    revision = current_revision(connection)
    check_not_ahead(scripts, revision)
    check_no_invalid_indexes(connection, schemas)

    head = scripts.get_current_head()
    if revision != head:
        if backup and settings.backup_dir is not None:
            _backup(connection, settings, settings.backup_dir, url, revision)
        _log.info("migration_started", source=revision, target=head)
        upgrade_to_head(connection, config)
        _log.info("migration_finished", revision=head)
    check_no_drift(connection, metadata, schemas)


def _backup(
    connection: Connection,
    settings: MigratorSettings,
    directory: Path,
    url: URL,
    revision: str | None,
) -> None:
    """Take and prune the dumps before an upgrade.

    Args:
        connection: Connection - The run's connection.
        settings: MigratorSettings - Backup settings.
        directory: Path - Dump directory.
        url: URL - The database.
        revision: str | None - Current revision.

    Raises:
        BackupError: If `pg_dump` is older than the server.

    """
    server = server_major(connection)
    client = client_major(settings.pg_dump)
    if client < server:
        msg = f"pg_dump {client} cannot dump a PostgreSQL {server} server"
        raise BackupError(msg)
    dump = take_backup(url, settings.pg_dump, directory, revision)
    removed = prune_backups(directory, settings.backup_keep)
    _log.info("backup_taken", path=str(dump), removed=[str(path) for path in removed])
