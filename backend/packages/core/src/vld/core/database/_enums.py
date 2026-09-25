"""Native PostgreSQL enum with labels from the values of the enumeration members."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum

if TYPE_CHECKING:
    from enum import StrEnum

    from sqlalchemy import MetaData


class PostgresEnum:
    """Native PostgreSQL enum with labels from the values of the enumeration members."""

    enum_cls: type[StrEnum]
    name: str
    metadata: MetaData

    def __init__(
        self,
        enum_cls: type[StrEnum],
        name: str,
        *,
        metadata: MetaData,
    ) -> None:
        self.enum_cls = enum_cls
        self.name = name
        self.metadata = metadata

    @classmethod
    def _labels_from_values(cls, enum_cls: type[StrEnum]) -> list[str]:
        """Labels of the PG type — values of the enumeration members.

        Args:
            enum_cls: type[StrEnum] - Domain enumeration class.

        Returns:
            list[str] - Values of the members in the order of declaration.

        """
        return [member.value for member in enum_cls]

    def __call__(self) -> Enum:
        """Create the enum.

        Returns:
            Enum - SQLAlchemy type, attached to the MetaData of the domain.

        """
        return Enum(
            self.enum_cls,
            name=self.name,
            metadata=self.metadata,
            values_callable=self._labels_from_values,
        )
