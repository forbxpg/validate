"""Helpers that revision files call."""

from __future__ import annotations

import pytest

from vld.migrator.ops import IrreversibleMigrationError, irreversible


def test_an_irreversible_downgrade_names_its_revision() -> None:
    """The operator learns which revision to restore past."""
    with pytest.raises(IrreversibleMigrationError, match="r3"):
        irreversible("r3")
