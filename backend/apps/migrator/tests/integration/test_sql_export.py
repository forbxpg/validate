"""Offline SQL per revision, the input of the migration linter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vld.migrator._sql_export import export_revision_sql

if TYPE_CHECKING:
    from pathlib import Path

    from alembic.config import Config

pytestmark = pytest.mark.usefixtures("app_role")


@pytest.fixture
def app_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Name the app role the probe revisions grant to; no database is needed."""
    monkeypatch.setenv("MIGRATOR_APP_ROLE", "vld_test_app")


def test_each_revision_gets_its_own_file_without_the_version_table(
    config: Config,
    tmp_path: Path,
) -> None:
    """Alembic's own table is not ours to lint; each revision is one transaction."""
    written = export_revision_sql(config, tmp_path)

    assert [path.name for path in written] == [
        "0000_r1.sql",
        "0001_r2.sql",
        "0002_r3.sql",
    ]
    first = written[0].read_text(encoding="utf-8")
    assert "CREATE SCHEMA probe" in first
    assert "CREATE TABLE vld_meta.alembic_version" not in first
    assert all("BEGIN;" not in path.read_text(encoding="utf-8") for path in written)


def test_a_revision_declares_the_rules_it_breaks_on_purpose(
    config: Config,
    tmp_path: Path,
) -> None:
    """A contract step that drops a column says so instead of disabling the rule."""
    written = export_revision_sql(config, tmp_path)

    assert (
        written[2]
        .read_text(encoding="utf-8")
        .startswith("-- squawk-ignore-file ban-drop-column\n")
    )
    assert not written[1].read_text(encoding="utf-8").startswith("-- squawk-ignore")
