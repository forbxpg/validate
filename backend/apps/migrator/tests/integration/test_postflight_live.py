"""The migrated database must match the models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from sqlalchemy import BigInteger, Column, Identity, Table, Text

from vld.core.database import make_metadata
from vld.migrator import SchemaDriftError, target_metadata
from vld.migrator._postflight import check_no_drift

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy import Connection

pytestmark = pytest.mark.integration


def test_the_head_matches_the_models(connection: Connection, config: Config) -> None:
    """Revisions and models agree, identity columns included."""
    config.attributes["connection"] = connection
    command.upgrade(config, "head")

    check_no_drift(connection, target_metadata(config), frozenset({"probe"}))


def test_a_model_without_a_revision_is_drift(
    connection: Connection,
    config: Config,
) -> None:
    """A column added to the models but not to the revisions fails the run."""
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    changed = make_metadata("probe")
    _ = Table(
        "items",
        changed,
        Column("id", BigInteger, Identity(), primary_key=True),
        Column("name", Text, nullable=False),
        Column("forgotten", Text),
    )

    with pytest.raises(SchemaDriftError, match="forgotten"):
        check_no_drift(connection, (changed,), frozenset({"probe"}))
