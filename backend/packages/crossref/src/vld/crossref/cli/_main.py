"""The entry point `vld-crossref`, safe to run without the `cli` extra."""

from __future__ import annotations

import sys

EXIT_MISSING_EXTRA = 2
_CLI_PACKAGES = frozenset({"typer", "click", "rich", "dotenv"})


def main() -> None:
    """Run `vld-crossref`; without the `cli` extra say how to install it.

    `[project.scripts]` is installed with or without extras, so the command
    exists either way.

    Raises:
        ModuleNotFoundError: If a module other than the extra is missing.
        SystemExit: With code 2 when the extra is missing.

    """
    try:
        from ._app import app  # ruff: ignore[import-outside-top-level] -- typer is optional; imported only when the command runs
    except ModuleNotFoundError as error:
        if (error.name or "").partition(".")[0] not in _CLI_PACKAGES:
            raise
        _ = sys.stderr.write(
            "vld-crossref needs the cli extra: pip install 'vld-crossref[cli]'\n",
        )
        raise SystemExit(EXIT_MISSING_EXTRA) from None
    app()
