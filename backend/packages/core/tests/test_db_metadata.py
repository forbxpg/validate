"""Тесты на архитектурные решения по БД."""

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
    md = make_metadata("billing")
    assert md.schema == "billing"


def test_metadata_carries_naming_convention() -> None:
    md = make_metadata("billing")
    assert md.naming_convention == NAMING_CONVENTION


def test_tables_land_in_domain_schema() -> None:
    md = make_metadata("billing")
    t = Table("deposits", md, Column("id", Integer, primary_key=True))
    assert t.schema == "billing"
    assert t.fullname == "billing.deposits"


def test_cross_domain_fk_is_structurally_impossible() -> None:
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
    md = make_metadata("billing")
    status_type = Enum("active", "refunded", name="deposit_status", metadata=md)
    _ = Table(
        "deposits",
        md,
        Column("id", Integer, primary_key=True),
        Column("status", status_type),
    )
    assert status_type.schema == "billing"  # pyright: ignore[reportUnknownMemberType]


def test_uuid_pk_is_generated_by_app_not_db() -> None:
    column = UUIDPkMixin.__dict__["id"].column
    assert column.default is not None
    generated = column.default.arg(None)
    assert isinstance(generated, uuid.UUID)
    assert generated.version == 4


def test_uuid_pk_has_server_default_as_safety_net() -> None:
    column = UUIDPkMixin.__dict__["id"].column
    assert column.server_default is not None
    assert "gen_random_uuid" in str(column.server_default.arg)


def test_core_exposes_no_shared_declarative_base() -> None:
    for name in dir(db_pkg):
        obj = getattr(db_pkg, name)
        if isinstance(obj, type) and issubclass(obj, DeclarativeBase):
            msg = (
                f"В core.database появился общий DeclarativeBase ({name}). "
                "Base объявляется в каждом домене — см. metadata.py."
            )
            pytest.fail(msg)
