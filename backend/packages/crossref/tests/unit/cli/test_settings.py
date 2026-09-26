"""Settings come from a flag, else the environment, else `.env` of the current folder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vld.crossref.cli._settings import resolve_settings

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("isolated")


def test_a_flag_beats_the_environment_and_the_environment_beats_dotenv(
    tmp_path: Path,
) -> None:
    """Three sources, one order."""
    _ = (tmp_path / ".env").write_text(
        "CROSSREF_MAILTO=file@example.org\nCROSSREF_OUTPUT_DIR=from-file\n",
    )

    from_file = resolve_settings(mailto=None, out_dir=None, cwd=tmp_path, environ={})
    from_env = resolve_settings(
        mailto=None,
        out_dir=None,
        cwd=tmp_path,
        environ={"CROSSREF_MAILTO": "env@example.org"},
    )
    from_flag = resolve_settings(
        mailto="flag@example.org",
        out_dir=tmp_path / "flag",
        cwd=tmp_path,
        environ={"CROSSREF_MAILTO": "env@example.org"},
    )

    assert (from_file.mailto, from_file.output_dir.name) == (
        "file@example.org",
        "from-file",
    )
    assert from_env.mailto == "env@example.org"
    assert (from_flag.mailto, from_flag.output_dir) == (
        "flag@example.org",
        tmp_path / "flag",
    )


def test_without_settings_the_public_pool_and_a_local_folder(tmp_path: Path) -> None:
    """No address, files under ./crossref-output."""
    settings = resolve_settings(mailto=None, out_dir=None, cwd=tmp_path, environ={})

    assert settings.mailto is None
    assert settings.plus_token is None
    assert settings.output_dir == tmp_path / "crossref-output"


def test_dotenv_of_a_parent_folder_is_not_read(tmp_path: Path) -> None:
    """A command run inside another project keeps out of its settings."""
    _ = (tmp_path / ".env").write_text("CROSSREF_MAILTO=parent@example.org\n")
    child = tmp_path / "child"
    child.mkdir()

    assert (
        resolve_settings(mailto=None, out_dir=None, cwd=child, environ={}).mailto
        is None
    )


def test_blank_values_count_as_missing(tmp_path: Path) -> None:
    """An empty variable does not ask for an empty address."""
    settings = resolve_settings(
        mailto=None,
        out_dir=None,
        cwd=tmp_path,
        environ={"CROSSREF_MAILTO": "  ", "CROSSREF_PLUS_TOKEN": ""},
    )

    assert (settings.mailto, settings.plus_token) == (None, None)
