"""MetaData and naming convention for domain schemas."""

from __future__ import annotations

from sqlalchemy import MetaData

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def make_metadata(schema: str) -> MetaData:
    """Create MetaData for the domain schema.

    Args:
        schema: str - The name of the PostgreSQL domain schema, e.g. ``"billing"``.

    Returns:
        MetaData - MetaData with the schema and naming convention.

    """
    return MetaData(schema=schema, naming_convention=NAMING_CONVENTION)
