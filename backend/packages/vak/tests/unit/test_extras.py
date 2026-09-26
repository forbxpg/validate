"""Without the parser extra the result still imports and the parser names the extra."""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import] -- our own interpreter
import sys

# A fresh interpreter where pdfplumber cannot be imported, as without the extra.
_WITHOUT_PDFPLUMBER = "import sys; sys.modules['pdfplumber'] = None; "


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- our own code
        [sys.executable, "-c", _WITHOUT_PDFPLUMBER + code],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_result_imports_without_the_parser_extra() -> None:
    """A reader of stored JSON needs pydantic only."""
    run = _run("import vld.vak, vld.vak.models, vld.vak.errors")

    assert run.returncode == 0, run.stderr


def test_the_parser_names_its_extra() -> None:
    """Importing the parser without pdfplumber says what to install."""
    run = _run("import vld.vak.parser")

    assert run.returncode != 0
    assert "pip install 'vld-vak[parser]'" in run.stderr
