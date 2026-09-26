"""A migrated PostgreSQL for integration tests: made by `vld-migrate`, dropped after."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import NullPool, create_engine, make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from vld.auth.infrastructure.models import QUALIFIED_OUTBOX, QUALIFIED_USERS
from vld.migrator import main as migrate

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from sqlalchemy import URL
    from sqlalchemy.ext.asyncio import AsyncEngine

_ALEMBIC_INI = Path(__file__).parents[4] / "alembic.ini"
_APP_ROLE = "vld_test_app"


@pytest.fixture(scope="session")
def migrated_url() -> Iterator[URL]:
    """Create a `test_auth_*` database, migrate it with `vld-migrate`, drop it after."""
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("TEST_DATABASE_URL is not set")
    admin_url = make_url(raw).set(drivername="postgresql+psycopg")
    name = f"test_auth_{uuid.uuid4().hex[:12]}"
    admin = create_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        _ = connection.execute(text(f"CREATE DATABASE {name}"))
        if not connection.scalar(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": _APP_ROLE},
        ):
            _ = connection.execute(text(f"CREATE ROLE {_APP_ROLE} NOLOGIN"))
    url = make_url(raw).set(database=name)
    try:
        with pytest.MonkeyPatch.context() as env:
            env.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
            env.setenv("MIGRATOR_APP_ROLE", _APP_ROLE)
            assert (
                migrate(["--config", str(_ALEMBIC_INI), "upgrade", "--no-backup"]) == 0
            )
        yield url
    finally:
        with admin.connect() as connection:
            _ = connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
        admin.dispose()


@pytest.fixture
async def db_engine(migrated_url: URL) -> AsyncIterator[AsyncEngine]:
    """Give an engine on the migrated database, emptying the auth tables after."""
    engine = create_async_engine(migrated_url, poolclass=NullPool)
    yield engine
    async with engine.begin() as connection:
        # The audit log is append-only by trigger; its rows stay.
        _ = await connection.execute(
            text(f"TRUNCATE {QUALIFIED_USERS}, {QUALIFIED_OUTBOX} CASCADE"),
        )
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Give a session whose transaction is rolled back after the test."""
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
