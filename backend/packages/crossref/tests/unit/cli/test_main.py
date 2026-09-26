"""The entry point without the cli extra says how to install it."""

from __future__ import annotations

import sys

import pytest

from vld.crossref.cli import main

pytestmark = pytest.mark.usefixtures("isolated")


def test_without_typer_the_command_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`[project.scripts]` exists without extras; it must not end in a traceback."""
    for name in list(sys.modules):
        if name.startswith(("vld.crossref.cli._", "typer")):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "typer", None)

    with pytest.raises(SystemExit) as exited:
        main()

    assert exited.value.code == 2
    assert "pip install 'vld-crossref[cli]'" in capsys.readouterr().err


def test_a_missing_module_of_our_own_is_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the optional packages turn into the hint; our own bugs stay loud."""
    for name in list(sys.modules):
        if name.startswith("vld.crossref.cli._"):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "vld.crossref.cli._works", None)

    with pytest.raises(ModuleNotFoundError):
        main()
