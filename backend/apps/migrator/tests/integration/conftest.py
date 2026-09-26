"""A fresh PostgreSQL database per test, migrated with the probe revisions."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic.config import Config
from sqlalchemy import (
    BigInteger,
    Column,
    Identity,
    NullPool,
    Table,
    Text,
    create_engine,
    make_url,
    text,
)

import vld.migrator
from vld.core.database import make_metadata
from vld.migrator._connection import migration_connection
from vld.migrator._settings import MigratorSettings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import URL, Connection, Engine

APP_ROLE = "vld_test_app"
_REVISIONS = Path(__file__).parent / "revisions"

PROBE_METADATA = make_metadata("probe")
_ = Table(
    "items",
    PROBE_METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("name", Text, nullable=False),
)
"""Models of the probe domain as they stand at the head of the test revisions."""


def _admin_url() -> URL:
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("TEST_DATABASE_URL is not set")
    return make_url(raw).set(drivername="postgresql+psycopg")


@pytest.fixture
def database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[URL]:
    """Create an empty `test_migrator_*` database and the app role, drop it after."""
    admin_url = _admin_url()
    name = f"test_migrator_{uuid.uuid4().hex[:12]}"
    admin = create_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        _ = connection.execute(text(f"CREATE DATABASE {name}"))
        exists = connection.scalar(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": APP_ROLE},
        )
        if not exists:
            _ = connection.execute(text(f"CREATE ROLE {APP_ROLE} NOLOGIN"))
    monkeypatch.setenv("MIGRATOR_APP_ROLE", APP_ROLE)
    try:
        yield admin_url.set(database=name)
    finally:
        with admin.connect() as connection:
            _ = connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
        admin.dispose()


@pytest.fixture
def settings(tmp_path: Path) -> MigratorSettings:
    """Give settings with short timeouts and a backup directory of its own."""
    return MigratorSettings(
        app_role=APP_ROLE,
        backup_dir=tmp_path / "backups",
        pg_dump=os.environ.get("MIGRATOR_PG_DUMP", "pg_dump"),
        lock_wait_seconds=0.2,
        lock_timeout_ms=200,
        statement_timeout_ms=10_000,
    )


@pytest.fixture
def engine(database_url: URL) -> Iterator[Engine]:
    """Give an engine on the test database."""
    engine = create_engine(database_url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(engine: Engine, settings: MigratorSettings) -> Iterator[Connection]:
    """Give the migration connection with its session timeouts."""
    with migration_connection(engine, settings) as connection:
        yield connection


@pytest.fixture
def config() -> Config:
    """Point Alembic at the migrator's env.py and the probe revisions."""
    config = Config()
    config.set_main_option("script_location", str(Path(vld.migrator.__file__).parent))
    config.set_main_option("version_locations", str(_REVISIONS))
    config.set_main_option("path_separator", "os")
    config.attributes["target_metadata"] = (PROBE_METADATA,)
    return config
