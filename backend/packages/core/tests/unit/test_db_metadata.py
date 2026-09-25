"""Database layout decisions: a schema per domain, no shared declarative base."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Column, Enum, ForeignKey, Integer, Table
from sqlalchemy.exc import NoReferencedTableError
from sqlalchemy.orm import DeclarativeBase

from vld.core import database as db_pkg
from vld.core.database import NAMING_CONVENTION, make_metadata
from vld.core.database.mixins import UUIDPkMixin


def test_metadata_carries_schema() -> None:
    """Tables of a domain land in its own PostgreSQL schema."""
    md = make_metadata("billing")
    assert md.schema == "billing"


def test_metadata_carries_naming_convention() -> None:
    """Constraints get predictable names that migrations can refer to."""
    md = make_metadata("billing")
    assert md.naming_convention == NAMING_CONVENTION


def test_tables_land_in_domain_schema() -> None:
    """A table is qualified by the domain schema without saying so."""
    md = make_metadata("billing")
    t = Table("deposits", md, Column("id", Integer, primary_key=True))
    assert t.schema == "billing"
    assert t.fullname == "billing.deposits"


def test_cross_domain_fk_is_structurally_impossible() -> None:
    """A foreign key into another domain's metadata cannot resolve."""
    auth_md = make_metadata("auth")
    billing_md = make_metadata("billing")
    _ = Table("users", auth_md, Column("id", Integer, primary_key=True))
    subs = Table(
        "subscriptions",
        billing_md,
        Column("id", Integer, primary_key=True),
        Column("user_id", Integer, ForeignKey("auth.users.id")),
    )

    with pytest.raises(NoReferencedTableError):
        _ = next(iter(subs.foreign_keys)).column


def test_intra_domain_fk_works() -> None:
    """Foreign keys inside one domain resolve as usual."""
    md = make_metadata("billing")
    _ = Table("deposits", md, Column("id", Integer, primary_key=True))
    entries = Table(
        "ledger_entries",
        md,
        Column("id", Integer, primary_key=True),
        Column("deposit_id", Integer, ForeignKey("billing.deposits.id")),
    )
    fk = next(iter(entries.foreign_keys))
    assert fk.column.table.fullname == "billing.deposits"


def test_pg_enum_inherits_domain_schema() -> None:
    """A PostgreSQL enum type lives in the schema of its domain."""
    md = make_metadata("billing")
    status_type = Enum("active", "refunded", name="deposit_status", metadata=md)
    _ = Table(
        "deposits",
        md,
        Column("id", Integer, primary_key=True),
        Column("status", status_type),
    )
    assert status_type.schema == "billing"


def test_uuid_pk_is_generated_by_app_not_db() -> None:
    """The application knows the id before the insert."""
    column = UUIDPkMixin.__dict__["id"].column
    assert column.default is not None
    generated = column.default.arg(None)
    assert isinstance(generated, uuid.UUID)
    assert generated.version == 4


def test_uuid_pk_has_server_default_as_safety_net() -> None:
    """Raw SQL inserts still get an id from the database."""
    column = UUIDPkMixin.__dict__["id"].column
    assert column.server_default is not None
    assert "gen_random_uuid" in str(column.server_default.arg)


def test_core_exposes_no_shared_declarative_base() -> None:
    """Each domain declares its own base, so metadata never mixes."""
    for name in dir(db_pkg):
        obj = getattr(db_pkg, name)
        if isinstance(obj, type) and issubclass(obj, DeclarativeBase):
            msg = f"core.database exports a shared DeclarativeBase ({name})"
            pytest.fail(msg)
