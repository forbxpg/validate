"""Upgrade to head, retrying only what another session caused."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from alembic import command
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    from collections.abc import Callable

    from alembic.config import Config
    from sqlalchemy import Connection

RETRY_DELAYS_SECONDS: tuple[float, ...] = (1.0, 3.0, 10.0)

_TRANSIENT_SQLSTATES = frozenset({
    "55P03",  # lock_not_available: lock_timeout fired
    "40P01",  # deadlock_detected
    "40001",  # serialization_failure
})

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


def upgrade_to_head(
    connection: Connection,
    config: Config,
    delays: tuple[float, ...] = RETRY_DELAYS_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Apply every pending revision, one transaction each.

    A revision that lost a lock race is rolled back and the run resumes from
    the current database revision; the revisions before it stay committed. A
    lost connection is not retried: the advisory lock went with it.

    Args:
        connection: Connection - The run's connection, outside a transaction.
        config: Config - Alembic configuration.
        delays: tuple[float, ...] - Pauses before each retry.
        sleep: Callable[[float], None] - How to pause.

    Raises:
        DBAPIError: If the error is not transient or the retries ran out.

    """
    config.attributes["connection"] = connection
    for attempt, delay in enumerate((*delays, None), start=1):
        try:
            command.upgrade(config, "head")
        except DBAPIError as error:
            connection.rollback()
            sqlstate = getattr(error.orig, "sqlstate", None)
            if delay is None or sqlstate not in _TRANSIENT_SQLSTATES:
                raise
            _log.warning(
                "migration_retry",
                attempt=attempt,
                sqlstate=sqlstate,
                delay_seconds=delay,
            )
            sleep(delay)
        else:
            return
