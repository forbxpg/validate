"""Declarative base of the journals models."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy.orm import DeclarativeBase

from vld.core.database import make_metadata

from ._tables import SCHEMA

if TYPE_CHECKING:
    from sqlalchemy import MetaData

METADATA = make_metadata(SCHEMA)


def fk(table: str, column: str = "id") -> str:
    """Name the target of a foreign key inside the schema.

    Args:
        table: str - The referred table.
        column: str - The referred column.

    Returns:
        str - ``journals.<table>.<column>``.

    """
    return f"{SCHEMA}.{table}.{column}"


class JournalsBase(DeclarativeBase):
    """Base of the journals ORM models."""

    metadata: ClassVar[MetaData] = METADATA
