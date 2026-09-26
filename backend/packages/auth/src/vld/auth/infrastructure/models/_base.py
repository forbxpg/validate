"""Declarative base of the auth models."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy.orm import DeclarativeBase

from vld.core.database import make_metadata

from ._tables import QUALIFIED_USERS, SCHEMA

if TYPE_CHECKING:
    from sqlalchemy import MetaData

METADATA = make_metadata(SCHEMA)

USERS_ID_FK = f"{QUALIFIED_USERS}.id"


class AuthBase(DeclarativeBase):
    """Base of the auth ORM models."""

    metadata: ClassVar[MetaData] = METADATA
