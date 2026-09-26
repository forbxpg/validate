"""What the migrator manages: the domain metadata and the version table schema."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from vld.auth.infrastructure import METADATA as AUTH_METADATA
from vld.core.audit import AUDIT_METADATA

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy import MetaData


VERSION_SCHEMA = "vld_meta"
"""Schema of `alembic_version`: global state of the chain, owned by no domain."""

DOMAIN_METADATA: tuple[MetaData, ...] = (AUDIT_METADATA, AUTH_METADATA)
"""Metadata of every domain with tables; a new domain adds its own here."""


def target_metadata(config: Config) -> tuple[MetaData, ...]:
    """Metadata the run compares against: the domains, or what a test passes.

    Args:
        config: Config - Alembic configuration of the run.

    Returns:
        tuple[MetaData, ...] - Metadata of the managed schemas.

    """
    return cast(
        "tuple[MetaData, ...]",
        config.attributes.get("target_metadata", DOMAIN_METADATA),
    )


def managed_schemas(metadata: tuple[MetaData, ...]) -> frozenset[str]:
    """Schemas the migrator compares and checks.

    Args:
        metadata: tuple[MetaData, ...] - Metadata of the domains.

    Returns:
        frozenset[str] - Their schema names.

    """
    return frozenset(item.schema for item in metadata if item.schema is not None)
