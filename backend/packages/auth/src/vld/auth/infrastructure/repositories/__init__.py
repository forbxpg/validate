"""Ports of the auth domain over SQLAlchemy, one module per store."""

from __future__ import annotations

from ._user import SqlAlchemyUserRepository

__all__ = ("SqlAlchemyUserRepository",)
