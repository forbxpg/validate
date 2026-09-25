"""The Alembic environment on a live PostgreSQL: stairway, commits, grants."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from vld.migrator._preflight import current_revision

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy import Connection

    from vld.migrator._settings import MigratorSettings

pytestmark = pytest.mark.integration


def test_stairway(connection: Connection, config: Config) -> None:
    """Every revision goes up, down unless irreversible, and up again."""
    config.attributes["connection"] = connection
    scripts = ScriptDirectory.from_config(config)
    for script in reversed(list(scripts.walk_revisions())):
        command.upgrade(config, script.revision)
        if not getattr(script.module, "irreversible", False):
            command.downgrade(config, "-1")
            command.upgrade(config, script.revision)

    assert current_revision(connection) == scripts.get_current_head()


def test_each_revision_commits_on_its_own(
    connection: Connection,
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing revision rolls back alone; the ones before it stay applied."""
    monkeypatch.setenv("PROBE_FAIL_R3", "1")
    config.attributes["connection"] = connection

    with pytest.raises(RuntimeError, match="r3 failed on purpose"):
        command.upgrade(config, "head")

    connection.rollback()
    assert current_revision(connection) == "r2"


def test_the_app_role_writes_rows_but_cannot_create_tables(
    connection: Connection,
    config: Config,
    settings: MigratorSettings,
) -> None:
    """The API role is limited to rows, even inside a domain schema."""
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    _ = connection.execute(text(f"SET ROLE {settings.app_role}"))
    _ = connection.execute(text("INSERT INTO probe.items (name) VALUES ('ok')"))

    with pytest.raises(ProgrammingError, match="permission denied"):
        _ = connection.execute(text("CREATE TABLE probe.intruder (id bigint)"))
    connection.rollback()
