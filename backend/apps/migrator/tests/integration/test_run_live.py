"""The whole run: checks, backup, upgrade, drift check."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vld.migrator import BackupError
from vld.migrator._backup import client_major, server_major
from vld.migrator._preflight import current_revision
from vld.migrator._run import run_check, run_upgrade

if TYPE_CHECKING:
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import Connection

    from vld.migrator._settings import MigratorSettings

pytestmark = pytest.mark.integration


def test_a_run_reaches_head_and_a_second_run_changes_nothing(
    connection: Connection,
    config: Config,
    settings: MigratorSettings,
) -> None:
    """The deploy may run the migrator every time, pending revisions or not."""
    url = connection.engine.url
    run_upgrade(connection, config, settings, url, backup=False)
    run_upgrade(connection, config, settings, url, backup=False)

    assert current_revision(connection) == "r3"
    assert run_check(connection, config) == "r3"


def test_a_backup_is_required_unless_refused_explicitly(
    connection: Connection,
    config: Config,
    settings: MigratorSettings,
) -> None:
    """Forgetting MIGRATOR_BACKUP_DIR must not silently skip the dump."""
    no_directory = settings.model_copy(update={"backup_dir": None})

    with pytest.raises(BackupError, match="MIGRATOR_BACKUP_DIR"):
        run_upgrade(
            connection, config, no_directory, connection.engine.url, backup=True
        )


def test_an_old_pg_dump_is_refused_before_anything_changes(
    connection: Connection,
    config: Config,
    settings: MigratorSettings,
    tmp_path: Path,
) -> None:
    """A dump by an older client would fail halfway; refuse before starting."""
    fake = tmp_path / "pg_dump"
    _ = fake.write_text(
        "#!/bin/sh\necho 'pg_dump (PostgreSQL) 9.6'\n", encoding="utf-8"
    )
    fake.chmod(0o755)
    old = settings.model_copy(update={"pg_dump": str(fake)})

    with pytest.raises(BackupError, match="cannot dump"):
        run_upgrade(connection, config, old, connection.engine.url, backup=True)
    assert current_revision(connection) is None


def test_the_dump_is_taken_at_the_old_revision(
    connection: Connection,
    config: Config,
    settings: MigratorSettings,
) -> None:
    """The dump restores the state before the upgrade, and old dumps are pruned."""
    if client_major(settings.pg_dump) < server_major(connection):
        pytest.skip("pg_dump is older than the server; set MIGRATOR_PG_DUMP")
    assert settings.backup_dir is not None

    run_upgrade(connection, config, settings, connection.engine.url, backup=True)

    assert [dump.name[-10:] for dump in settings.backup_dir.glob("*.dump")] == [
        "-base.dump"
    ]
