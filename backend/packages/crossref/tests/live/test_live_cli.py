"""The command line against the real Crossref (marked crossref_live)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from vld.crossref.cli._app import app

pytestmark = pytest.mark.crossref_live


def test_works_get_reads_a_real_work(live_mailto: str | None) -> None:
    """`vld-crossref works get … --json` end to end."""
    args = ["works", "get", "10.1103/PhysRevLett.1.1", "--json"]
    if live_mailto:
        args += ["--mailto", live_mailto]

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["container-title"] == ["Physical Review Letters"]
