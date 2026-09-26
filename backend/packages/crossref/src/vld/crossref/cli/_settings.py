"""Where the command line takes its settings: flags, the environment, `.env`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import dotenv_values

if TYPE_CHECKING:
    from collections.abc import Mapping

MAILTO_VARIABLE = "CROSSREF_MAILTO"
PLUS_TOKEN_VARIABLE = "CROSSREF_PLUS_TOKEN"  # ruff: ignore[hardcoded-password-string] -- a variable name, not a secret
OUTPUT_DIR_VARIABLE = "CROSSREF_OUTPUT_DIR"
DEFAULT_OUTPUT_DIR = "crossref-output"
"""Folder of saved files under the current one when nothing else is set."""


@dataclass(frozen=True, slots=True)
class CliSettings:
    """Settings of one run.

    Attributes:
        mailto: str | None - Address for the polite pool; None asks for the public one.
        plus_token: str | None - Crossref Plus token, if any.
        output_dir: Path - Folder of saved files.

    """

    mailto: str | None
    plus_token: str | None
    output_dir: Path


def resolve_settings(
    *,
    mailto: str | None,
    out_dir: Path | None,
    cwd: Path,
    environ: Mapping[str, str],
) -> CliSettings:
    """Take each setting from a flag, else the environment, else `.env` of `cwd`.

    Only `.env` of the current folder is read: a command run inside another
    project must not pick up the settings of its parents.

    Args:
        mailto: str | None - `--mailto`.
        out_dir: Path | None - `--out-dir`.
        cwd: Path - The current folder.
        environ: Mapping[str, str] - The environment.

    Returns:
        CliSettings - The settings.

    """
    dotenv = cwd / ".env"
    from_file = (
        {key: value for key, value in dotenv_values(dotenv).items() if value}
        if dotenv.is_file()
        else {}
    )

    def pick(variable: str) -> str | None:
        value = environ.get(variable) or from_file.get(variable)
        return value.strip() or None if value else None

    folder = out_dir or (
        Path(chosen) if (chosen := pick(OUTPUT_DIR_VARIABLE)) else None
    )
    return CliSettings(
        mailto=mailto or pick(MAILTO_VARIABLE),
        plus_token=pick(PLUS_TOKEN_VARIABLE),
        output_dir=(folder or cwd / DEFAULT_OUTPUT_DIR).expanduser(),
    )
