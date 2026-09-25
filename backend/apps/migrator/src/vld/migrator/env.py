"""Alembic environment: one chain for every domain, one transaction per revision."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from alembic import context
from sqlalchemy import Connection, text

from vld.core.config import DatabaseSettings
from vld.migrator import (
    VERSION_SCHEMA,
    create_migration_engine,
    managed_schemas,
    target_metadata,
)

if TYPE_CHECKING:
    from sqlalchemy import MetaData

_config = context.config
_metadata = target_metadata(_config)
_schemas = managed_schemas(_metadata)


def _include_name(name: str | None, type_: str, _parents: object) -> bool:
    """Compare only the domain schemas: the rest of the database is not ours.

    Args:
        name: str | None - Object name.
        type_: str - Object kind.
        _parents: object - Names of the parent objects.

    Returns:
        bool - True for everything except a schema that is not a domain's.

    """
    return type_ != "schema" or name in _schemas


def _configure(**options: object) -> None:
    """Configure the context with the settings shared by every mode.

    Args:
        options: object - Connection or offline dialect.

    """
    context.configure(
        target_metadata=cast("MetaData", cast("object", list(_metadata))),
        include_schemas=True,
        include_name=_include_name,
        version_table_schema=VERSION_SCHEMA,
        transaction_per_migration=True,
        **options,  # pyright: ignore[reportArgumentType]
    )


def _run(connection: Connection) -> None:
    """Run the migrations on a connection that is outside a transaction.

    Args:
        connection: Connection - Connection of the migrator role.

    """
    _ = connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {VERSION_SCHEMA}"))
    # Committed before configure: Alembic takes a connection in a transaction for
    # an external one and then never commits per revision.
    connection.commit()
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    _configure(dialect_name="postgresql", literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    shared = _config.attributes.get("connection")
    if isinstance(shared, Connection):
        _run(shared)
    else:
        engine = create_migration_engine(DatabaseSettings())  # pyright: ignore[reportCallIssue] -- required, read from the environment
        with engine.connect() as own:
            _run(own)
        engine.dispose()
