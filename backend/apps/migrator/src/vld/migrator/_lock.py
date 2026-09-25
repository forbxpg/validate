"""One migration run at a time, through a session-level advisory lock."""

from __future__ import annotations

import contextlib
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, cast

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ._errors import MigrationLockBusyError

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import Connection

MIGRATION_LOCK_KEY = 0x766C_645F_6D69_6772
"""Advisory lock key of vld-migrate, the ASCII of `vld_migr`."""

_POLL_SECONDS = 1.0


@contextmanager
def migration_lock(connection: Connection, wait_seconds: float) -> Generator[None]:
    """Hold the migration lock for the whole run.

    Session level, not transaction level: it must survive the per-revision
    commits and autocommit blocks. PostgreSQL drops it if the process dies.

    Args:
        connection: Connection - The run's connection.
        wait_seconds: float - How long to wait for another run.

    Yields:
        None - While the lock is held.

    Raises:
        MigrationLockBusyError: If another run still holds the lock after the wait.

    """
    deadline = time.monotonic() + wait_seconds
    while not _try_lock(connection):
        if time.monotonic() >= deadline:
            msg = f"another migration run holds the lock after {wait_seconds} s"
            raise MigrationLockBusyError(msg)
        time.sleep(_POLL_SECONDS)
    try:
        yield
    finally:
        # A broken connection has already lost the lock together with the session.
        with contextlib.suppress(DBAPIError):
            connection.rollback()
            _ = connection.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": MIGRATION_LOCK_KEY},
            )
            connection.commit()


def _try_lock(connection: Connection) -> bool:
    """Try to take the lock once, without waiting.

    Args:
        connection: Connection - The run's connection.

    Returns:
        bool - True if the lock is now held by this session.

    """
    taken = cast(
        "bool",
        connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": MIGRATION_LOCK_KEY},
        ),
    )
    connection.commit()
    return taken
