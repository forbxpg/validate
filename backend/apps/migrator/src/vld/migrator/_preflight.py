"""Checks before a run: the scripts and the database must agree."""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic.runtime.migration import MigrationContext
from alembic.util import CommandError
from sqlalchemy import bindparam, text

from ._errors import PreflightError
from ._layout import VERSION_SCHEMA

if TYPE_CHECKING:
    from alembic.script import ScriptDirectory
    from sqlalchemy import Connection

_INVALID_INDEXES = text(
    """
    SELECT n.nspname || '.' || c.relname
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE NOT i.indisvalid AND n.nspname IN :schemas
    ORDER BY 1
    """,
).bindparams(bindparam("schemas", expanding=True))


def current_revision(connection: Connection) -> str | None:
    """Read the revision the database is at.

    Args:
        connection: Connection - The run's connection.

    Returns:
        str | None - The revision, or None for a database never migrated.

    """
    context = MigrationContext.configure(
        connection,
        opts={"version_table_schema": VERSION_SCHEMA},
    )
    revision = context.get_current_revision()
    connection.commit()
    return revision


def check_single_head(scripts: ScriptDirectory) -> None:
    """Refuse a chain that branched: two heads have no defined order.

    Args:
        scripts: ScriptDirectory - Revisions of every domain.

    Raises:
        PreflightError: If the scripts have more than one head.

    """
    heads = scripts.get_heads()
    if len(heads) > 1:
        msg = f"the revision chain has {len(heads)} heads: {sorted(heads)}; merge them"
        raise PreflightError(msg)


def check_not_ahead(scripts: ScriptDirectory, revision: str | None) -> None:
    """Refuse a database migrated by newer code than this one.

    Args:
        scripts: ScriptDirectory - Revisions this code knows.
        revision: str | None - The database revision.

    Raises:
        PreflightError: If this code does not know the database revision.

    """
    if revision is None:
        return
    try:
        _ = scripts.get_revision(revision)
    except CommandError as error:
        msg = (
            f"the database is at revision {revision}, unknown to this code: "
            "it was migrated by a newer release"
        )
        raise PreflightError(msg) from error


def check_no_invalid_indexes(connection: Connection, schemas: frozenset[str]) -> None:
    """Refuse to run over indexes left invalid by a failed concurrent build.

    Args:
        connection: Connection - The run's connection.
        schemas: frozenset[str] - Domain schemas.

    Raises:
        PreflightError: If any domain schema has an invalid index.

    """
    if not schemas:
        return
    invalid = list(connection.scalars(_INVALID_INDEXES, {"schemas": sorted(schemas)}))
    connection.commit()
    if invalid:
        msg = f"invalid indexes left by a failed build, drop them first: {invalid}"
        raise PreflightError(msg)
