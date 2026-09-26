"""Fixtures for tests against a live PostgreSQL."""

from __future__ import annotations

from live_db import db_engine, migrated_url

__all__ = ("db_engine", "migrated_url")
