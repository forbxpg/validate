"""Lock races with the running application are retried, other errors are not."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from vld.migrator._preflight import current_revision
from vld.migrator._upgrade import upgrade_to_head

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy import Connection, Engine

pytestmark = pytest.mark.integration


def test_a_lock_timeout_is_retried_until_the_table_is_free(
    engine: Engine,
    connection: Connection,
    config: Config,
) -> None:
    """A revision that waits on a busy table gives up, then succeeds on retry."""
    config.attributes["connection"] = connection
    command.upgrade(config, "r1")
    blocker = engine.connect()
    _ = blocker.execute(text("LOCK TABLE probe.items IN ACCESS SHARE MODE"))
    retries: list[float] = []

    def _release(delay: float) -> None:
        retries.append(delay)
        blocker.rollback()

    upgrade_to_head(connection, config, delays=(0.0,), sleep=_release)
    blocker.close()

    assert retries == [0.0]
    assert current_revision(connection) == "r3"


def test_a_lock_timeout_without_retries_left_is_final(
    engine: Engine,
    connection: Connection,
    config: Config,
) -> None:
    """The failed revision rolls back and the database stays where it was."""
    config.attributes["connection"] = connection
    command.upgrade(config, "r1")
    blocker = engine.connect()
    _ = blocker.execute(text("LOCK TABLE probe.items IN ACCESS SHARE MODE"))

    with pytest.raises(DBAPIError) as caught:
        upgrade_to_head(connection, config, delays=())
    blocker.close()

    assert getattr(caught.value.orig, "sqlstate", None) == "55P03"
    assert current_revision(connection) == "r1"
