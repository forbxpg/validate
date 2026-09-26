"""A migrated PostgreSQL for the journals schema, and connections as owner and as app."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import NullPool, create_engine, make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from vld.migrator import main as migrate

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from sqlalchemy import URL
    from sqlalchemy.ext.asyncio import AsyncConnection

_ALEMBIC_INI = Path(__file__).parents[4] / "alembic.ini"
APP_ROLE = "vld_test_app"


@pytest.fixture(scope="session")
def migrated_url() -> Iterator[URL]:
    """Create a `test_journals_*` database, migrate it with `vld-migrate`, drop it after."""
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("TEST_DATABASE_URL is not set")
    admin_url = make_url(raw).set(drivername="postgresql+psycopg")
    name = f"test_journals_{uuid.uuid4().hex[:12]}"
    admin = create_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        _ = connection.execute(text(f"CREATE DATABASE {name}"))
        if not connection.scalar(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": APP_ROLE},
        ):
            _ = connection.execute(text(f"CREATE ROLE {APP_ROLE} NOLOGIN"))
    url = make_url(raw).set(database=name)
    try:
        with pytest.MonkeyPatch.context() as env:
            env.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
            env.setenv("MIGRATOR_APP_ROLE", APP_ROLE)
            assert (
                migrate(["--config", str(_ALEMBIC_INI), "upgrade", "--no-backup"]) == 0
            )
        yield url
    finally:
        with admin.connect() as connection:
            _ = connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
        admin.dispose()


@pytest.fixture
async def owner(migrated_url: URL) -> AsyncIterator[AsyncConnection]:
    """Give a connection as the owner, in a transaction rolled back after the test."""
    engine = create_async_engine(migrated_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def app(owner: AsyncConnection) -> AsyncConnection:
    """Give the same connection acting as the app role until the rollback.

    Returns:
        AsyncConnection - The connection, `SET LOCAL ROLE` to the app role.

    """
    _ = await owner.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    return owner
