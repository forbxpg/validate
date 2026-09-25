"""`vld-migrate`: the command the deploy runs before the new code starts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from alembic.config import Config

from vld.core.config import DatabaseSettings, ObservabilitySettings
from vld.core.obs import configure_logging

from ._connection import create_migration_engine, migration_connection
from ._errors import MigratorError
from ._lock import migration_lock
from ._run import run_check, run_upgrade
from ._settings import MigratorSettings
from ._sql_export import export_revision_sql

if TYPE_CHECKING:
    from sqlalchemy import Engine

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Run `vld-migrate upgrade`, `check` or `export-sql`.

    Args:
        argv: list[str] | None - Arguments; the process arguments when None.

    Returns:
        int - Exit code: 0 on success, 1 on a refusal.

    """
    arguments = _parser().parse_args(argv, namespace=_Arguments())
    configure_logging(ObservabilitySettings())
    config = Config(str(arguments.config))
    if arguments.command == "export-sql":
        written = export_revision_sql(config, arguments.directory)
        _log.info("revision_sql_exported", files=[str(path) for path in written])
        return 0
    settings = MigratorSettings()  # pyright: ignore[reportCallIssue] -- required, read from the environment
    database = DatabaseSettings()  # pyright: ignore[reportCallIssue] -- required, read from the environment
    engine = create_migration_engine(database)
    try:
        _execute(arguments, settings, config, engine)
    except MigratorError as error:
        _log.error("migration_refused", reason=str(error), kind=type(error).__name__)
        return 1
    finally:
        engine.dispose()
    return 0


def _execute(
    arguments: _Arguments,
    settings: MigratorSettings,
    config: Config,
    engine: Engine,
) -> None:
    """Run the chosen command on the migration connection.

    Args:
        arguments: _Arguments - Parsed command line.
        settings: MigratorSettings - Migrator settings.
        config: Config - Alembic configuration.
        engine: Engine - Migration engine.

    """
    with migration_connection(engine, settings) as connection:
        if arguments.command == "check":
            revision = run_check(connection, config)
            _log.info("migration_check_passed", revision=revision)
            return
        with migration_lock(connection, settings.lock_wait_seconds):
            run_upgrade(
                connection,
                config,
                settings,
                engine.url,
                backup=not arguments.no_backup,
            )


class _Arguments(argparse.Namespace):
    """Parsed command line of `vld-migrate`.

    Attributes:
        command: str - `upgrade`, `check` or `export-sql`.
        config: Path - Alembic configuration file.
        no_backup: bool - Skip the dump before the upgrade.
        directory: Path - Where `export-sql` writes the files.

    """

    command: str = ""
    config: Path = Path("alembic.ini")
    no_backup: bool = False
    directory: Path = Path("migration-sql")


def _parser() -> argparse.ArgumentParser:
    """Describe the command line.

    Returns:
        argparse.ArgumentParser - Parser of `vld-migrate`.

    """
    parser = argparse.ArgumentParser(prog="vld-migrate")
    _ = parser.add_argument(
        "--config",
        type=Path,
        help="Alembic configuration (default: ./alembic.ini)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    upgrade = commands.add_parser("upgrade", help="check, back up, upgrade to head")
    _ = upgrade.add_argument(
        "--no-backup",
        action="store_true",
        help="skip the dump; only for local and CI databases",
    )
    _ = commands.add_parser("check", help="check without changing anything")
    export = commands.add_parser("export-sql", help="write each revision's SQL")
    _ = export.add_argument("directory", type=Path, help="output directory")
    return parser
