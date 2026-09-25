"""Checks before a run, against a live database."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from vld.migrator import PreflightError
from vld.migrator._preflight import (
    check_no_invalid_indexes,
    check_not_ahead,
    current_revision,
)

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy import Connection, Engine

pytestmark = pytest.mark.integration


def test_a_database_ahead_of_the_code_is_refused(
    connection: Connection,
    config: Config,
) -> None:
    """A rolled-back image must not run against a newer schema."""
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    _ = connection.execute(
        text("UPDATE vld_meta.alembic_version SET version_num = 'r9'")
    )
    connection.commit()

    with pytest.raises(PreflightError, match="newer release"):
        check_not_ahead(
            ScriptDirectory.from_config(config), current_revision(connection)
        )


def test_an_invalid_index_is_refused(
    engine: Engine,
    connection: Connection,
    config: Config,
) -> None:
    """An index left by a failed concurrent build must be dealt with first."""
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as other:
        _ = other.execute(text("INSERT INTO probe.items (name) VALUES ('a'), ('a')"))
        with pytest.raises(DBAPIError):
            _ = other.execute(
                text(
                    "CREATE UNIQUE INDEX CONCURRENTLY ix_items_name ON probe.items (name)"
                )
            )

    with pytest.raises(PreflightError, match=r"probe\.ix_items_name"):
        check_no_invalid_indexes(connection, frozenset({"probe"}))
