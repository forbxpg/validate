"""One migration run at a time."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from vld.migrator import MigrationLockBusyError
from vld.migrator._lock import MIGRATION_LOCK_KEY, migration_lock

if TYPE_CHECKING:
    from sqlalchemy import Connection, Engine

pytestmark = pytest.mark.integration


def test_a_second_run_waits_then_refuses(
    engine: Engine, connection: Connection
) -> None:
    """Two runs never migrate at once."""
    holder = engine.connect()
    _ = holder.execute(
        text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
    )

    with (
        pytest.raises(MigrationLockBusyError),
        migration_lock(connection, wait_seconds=0.2),
    ):
        pass
    holder.close()


def test_the_lock_is_free_again_after_a_run(
    engine: Engine, connection: Connection
) -> None:
    """A finished run leaves no lock behind for the next deploy."""
    with migration_lock(connection, wait_seconds=0):
        pass

    with engine.connect() as other:
        taken = other.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
        )
    assert taken is True
