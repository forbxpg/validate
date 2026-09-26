"""Helpers for revision files."""

from __future__ import annotations

import re
from typing import NoReturn

from alembic import op

from ._settings import MigratorSettings

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


class IrreversibleMigrationError(Exception):
    """The downgrade of this revision would lose data."""


def irreversible(revision: str) -> NoReturn:
    """Refuse the downgrade of a revision that loses data.

    Call it as the whole body of `downgrade()` and set `irreversible = True` in
    the revision module, so that the stairway test skips its downgrade.

    Args:
        revision: str - The revision id.

    Raises:
        IrreversibleMigrationError: Always.

    """
    msg = f"revision {revision} loses data; restore the backup instead"
    raise IrreversibleMigrationError(msg)


def app_role() -> str:
    """Name the role of the API, the one domain schemas grant their rows to.

    Returns:
        str - The role, from `MIGRATOR_APP_ROLE`.

    """
    return MigratorSettings().app_role  # pyright: ignore[reportCallIssue] -- required, read from the environment


def create_domain_schema(schema: str) -> None:
    """Create a domain schema and let the app role read and write its rows.

    Default privileges belong to the role that creates the tables, the migrator
    role, so every later table of the schema is covered too.

    Args:
        schema: str - Schema name, lower-case letters, digits and `_`.

    """
    role = app_role()
    _identifier(schema)
    op.execute(f"CREATE SCHEMA {schema}")
    op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
    tables = f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}"
    sequences = f"GRANT USAGE, SELECT ON SEQUENCES TO {role}"
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} {tables}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} {sequences}")


def drop_domain_schema(schema: str) -> None:
    """Undo `create_domain_schema` once the schema's tables are dropped.

    Args:
        schema: str - Schema name.

    """
    role = app_role()
    _identifier(schema)
    tables = f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {role}"
    sequences = f"REVOKE USAGE, SELECT ON SEQUENCES FROM {role}"
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} {sequences}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} {tables}")
    op.execute(f"DROP SCHEMA {schema}")


def _identifier(name: str) -> None:
    """Refuse a name that would need quoting inside SQL.

    Args:
        name: str - Schema name.

    Raises:
        ValueError: If the name is not a plain lower-case identifier.

    """
    if not _IDENTIFIER.fullmatch(name):
        msg = f"{name!r} is not a plain lower-case identifier"
        raise ValueError(msg)
