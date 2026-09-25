"""Migrator settings refuse values that would make a run unsafe."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vld.migrator._settings import MigratorSettings


def test_a_lock_timeout_the_statement_timeout_would_always_beat_is_refused() -> None:
    """With lock_timeout >= statement_timeout the lock timeout never fires."""
    with pytest.raises(ValidationError, match="LOCK_TIMEOUT"):
        _ = MigratorSettings(
            app_role="app",
            lock_timeout_ms=5000,
            statement_timeout_ms=1000,
        )


@pytest.mark.parametrize("role", ["App", "app-role", "app; DROP TABLE x", ""])
def test_an_app_role_that_would_need_quoting_is_refused(role: str) -> None:
    """The role name goes into DDL, so only plain lower-case names pass."""
    with pytest.raises(ValidationError):
        _ = MigratorSettings(app_role=role)
