"""The check after a run: the migrated database must match the models."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

from ._errors import SchemaDriftError
from ._layout import VERSION_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import Connection, MetaData


def check_no_drift(
    connection: Connection,
    metadata: tuple[MetaData, ...],
    schemas: frozenset[str],
) -> None:
    """Refuse a database that differs from the models after the upgrade.

    Autogenerate does not see renames, views or triggers: this is an alarm for
    a model changed without a revision, not a proof of equality.

    Args:
        connection: Connection - The run's connection.
        metadata: tuple[MetaData, ...] - Models of every domain.
        schemas: frozenset[str] - Domain schemas to compare.

    Raises:
        SchemaDriftError: If the database and the models differ.

    """
    context = MigrationContext.configure(
        connection,
        opts={
            "include_schemas": True,
            "include_name": _only_schemas(schemas),
            "version_table_schema": VERSION_SCHEMA,
        },
    )
    # Compared together: one metadata at a time would report the tables of the
    # other domains as extra. Alembic accepts a sequence; its annotation does not.
    differences = cast(
        "list[object]",
        compare_metadata(context, cast("MetaData", cast("object", list(metadata)))),
    )
    connection.commit()
    if differences:
        msg = f"the database differs from the models: {differences}"
        raise SchemaDriftError(msg)


def _only_schemas(schemas: frozenset[str]) -> Callable[[str | None, str, object], bool]:
    """Build the filter that keeps the comparison inside the domain schemas.

    Args:
        schemas: frozenset[str] - Domain schemas.

    Returns:
        Callable[[str | None, str, object], bool] - Alembic `include_name` hook.

    """

    def _include(name: str | None, type_: str, _parents: object) -> bool:
        return type_ != "schema" or name in schemas

    return _include
