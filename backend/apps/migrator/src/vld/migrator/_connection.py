"""The one dedicated connection a migration run works on."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import NullPool, create_engine, make_url

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import URL, Connection, Engine

    from vld.core.config import DatabaseSettings

    from ._settings import MigratorSettings


def migration_url(settings: DatabaseSettings) -> URL:
    """Point `DATABASE_URL` at the synchronous psycopg driver that Alembic uses.

    Args:
        settings: DatabaseSettings - Database settings of the migrator role.

    Returns:
        URL - The same database, through psycopg.

    """
    return make_url(str(settings.url)).set(drivername="postgresql+psycopg")


def create_migration_engine(settings: DatabaseSettings) -> Engine:
    """Create an engine without a pool: a run needs exactly one connection.

    Args:
        settings: DatabaseSettings - Database settings of the migrator role.

    Returns:
        Engine - Engine for the migration connection.

    """
    return create_engine(migration_url(settings), poolclass=NullPool)


@contextmanager
def migration_connection(
    engine: Engine,
    settings: MigratorSettings,
) -> Generator[Connection]:
    """Open the run's connection with its session timeouts.

    The connection is handed out outside a transaction: Alembic treats a
    connection already in a transaction as external and then never commits
    per revision.

    Args:
        engine: Engine - Migration engine.
        settings: MigratorSettings - Timeouts.

    Yields:
        Connection - Connection with `lock_timeout` and `statement_timeout` set.

    """
    with engine.connect() as connection:
        _ = connection.exec_driver_sql(f"SET lock_timeout = {settings.lock_timeout_ms}")
        _ = connection.exec_driver_sql(
            f"SET statement_timeout = {settings.statement_timeout_ms}",
        )
        _ = connection.exec_driver_sql(
            "SET idle_in_transaction_session_timeout = 60000",
        )
        _ = connection.exec_driver_sql("SET application_name = 'vld-migrate'")
        connection.commit()
        yield connection
