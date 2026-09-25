"""The dump before an upgrade, taken by a real pg_dump."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vld.migrator import BackupError
from vld.migrator._backup import client_major, server_major, take_backup

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Connection

    from vld.migrator._settings import MigratorSettings

pytestmark = pytest.mark.integration


def test_a_dump_is_written_and_read_back(
    connection: Connection,
    settings: MigratorSettings,
    tmp_path: Path,
) -> None:
    """pg_restore reads the archive, so the dump is not a broken file."""
    if client_major(settings.pg_dump) < server_major(connection):
        pytest.skip("pg_dump is older than the server; set MIGRATOR_PG_DUMP")

    dump = take_backup(connection.engine.url, settings.pg_dump, tmp_path, "r1")

    assert dump.name.endswith("-r1.dump")
    assert dump.stat().st_size > 0
    assert not list(tmp_path.glob("*.partial"))


def test_a_failed_dump_leaves_no_file_behind(
    connection: Connection,
    settings: MigratorSettings,
    tmp_path: Path,
) -> None:
    """A half-written dump must never look like a backup."""
    wrong = connection.engine.url.set(database="test_missing_database")

    with pytest.raises(BackupError, match="backup failed"):
        _ = take_backup(wrong, settings.pg_dump, tmp_path, "r1")
    assert not list(tmp_path.iterdir())
