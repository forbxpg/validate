"""SQL of every revision as its own file, for the migration linter."""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING, cast

from alembic import command
from alembic.script import ScriptDirectory

if TYPE_CHECKING:
    from pathlib import Path

    from alembic.config import Config

_REVISION_MARKER = re.compile(r"^-- Running upgrade .*-> (\S+)$", re.MULTILINE)
_TRANSACTION_LINES = frozenset({"BEGIN;", "COMMIT;"})


def export_revision_sql(config: Config, directory: Path) -> list[Path]:
    """Write the offline SQL of each revision to `<n>_<revision>.sql`.

    The text before the first revision is Alembic's own version table and is
    left out. A revision lists the linter rules it breaks on purpose in
    `squawk_ignore`, which becomes a `squawk-ignore-file` comment.

    Args:
        config: Config - Alembic configuration.
        directory: Path - Output directory, created if missing.

    Returns:
        list[Path] - The written files, in chain order.

    """
    buffer = io.StringIO()
    config.output_buffer = buffer
    command.upgrade(config, "head", sql=True)
    modules = {
        script.revision: script.module
        for script in ScriptDirectory.from_config(config).walk_revisions()
    }
    parts = _REVISION_MARKER.split(buffer.getvalue())[1:]
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, (revision, body) in enumerate(zip(parts[::2], parts[1::2], strict=True)):
        rules = cast("tuple[str, ...]", getattr(modules[revision], "squawk_ignore", ()))
        header = f"-- squawk-ignore-file {','.join(rules)}\n" if rules else ""
        # Each file is one revision, one transaction: the linter is told so with
        # --assume-in-transaction, and the BEGIN/COMMIT between revisions go.
        statements = "\n".join(
            line for line in body.strip().splitlines() if line not in _TRANSACTION_LINES
        )
        path = directory / f"{index:04d}_{revision}.sql"
        _ = path.write_text(f"{header}{statements.strip()}\n", encoding="utf-8")
        written.append(path)
    return written
