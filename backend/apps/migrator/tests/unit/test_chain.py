"""The revision chain: one head, in the real configuration and in a branched one."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import vld.migrator
from vld.migrator import PreflightError
from vld.migrator._preflight import check_single_head

_BACKEND = Path(__file__).resolve().parents[4]


def _revision(directory: Path, revision: str, down: str | None) -> None:
    lines = [
        f"revision = {revision!r}",
        f"down_revision = {down!r}",
        "branch_labels = None",
        "depends_on = None",
        "def upgrade(): pass",
        "def downgrade(): pass",
    ]
    _ = (directory / f"{revision}.py").write_text("\n".join(lines), encoding="utf-8")


def _scripts(versions: Path) -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(Path(vld.migrator.__file__).parent))
    config.set_main_option("version_locations", str(versions))
    config.set_main_option("path_separator", "os")
    return ScriptDirectory.from_config(config)


def test_the_real_chain_has_at_most_one_head() -> None:
    """Two domains branching the chain must fail CI, not the deploy."""
    scripts = ScriptDirectory.from_config(Config(str(_BACKEND / "alembic.ini")))

    assert len(scripts.get_heads()) <= 1


def test_a_branched_chain_is_refused(tmp_path: Path) -> None:
    """Two heads have no defined order between them."""
    _revision(tmp_path, "a1", None)
    _revision(tmp_path, "b1", None)

    with pytest.raises(PreflightError, match="2 heads"):
        check_single_head(_scripts(tmp_path))
