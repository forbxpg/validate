"""The dump taken before an upgrade, verified and kept for a restore."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import TYPE_CHECKING, cast

from sqlalchemy import text

from ._errors import BackupError

if TYPE_CHECKING:
    from sqlalchemy import URL, Connection

_VERSION = re.compile(r"\(PostgreSQL\) (\d+)")


def server_major(connection: Connection) -> int:
    """Read the major version of the server.

    Args:
        connection: Connection - The run's connection.

    Returns:
        int - Major version, e.g. 18.

    """
    number = cast("str", connection.scalar(text("SHOW server_version_num")))
    connection.commit()
    return int(number) // 10_000


def client_major(executable: str) -> int:
    """Read the major version of a PostgreSQL client program.

    Args:
        executable: str - `pg_dump` or `pg_restore`.

    Returns:
        int - Major version, e.g. 18.

    Raises:
        BackupError: If the program is missing or reports no version.

    """
    try:
        output = run(
            [executable, "--version"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout
    except (OSError, CalledProcessError) as error:
        msg = f"{executable} cannot run: {error}"
        raise BackupError(msg) from error
    match = _VERSION.search(output)
    if match is None:
        msg = f"{executable} reported no version: {output!r}"
        raise BackupError(msg)
    return int(match.group(1))


def take_backup(url: URL, pg_dump: str, directory: Path, revision: str | None) -> Path:
    """Dump the database and check that the archive can be read back.

    Args:
        url: URL - The database, with the migrator credentials.
        pg_dump: str - `pg_dump` executable; `pg_restore` is expected next to it.
        directory: Path - Where the dump goes.
        revision: str | None - Current revision, part of the file name.

    Returns:
        Path - The verified dump.

    Raises:
        BackupError: If the dump or its verification fails.

    """
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = directory / f"{stamp}-{revision or 'base'}.dump"
    partial = target.with_suffix(".partial")
    # The password travels in the environment, not on a command line `ps` shows.
    environment = {**os.environ, "PGPASSWORD": url.password or ""}
    # URL.set() ignores None, so the password is dropped with the NamedTuple API;
    # render_as_string() would otherwise put a literal "***" in its place.
    dsn = url._replace(drivername="postgresql", password=None).render_as_string(
        hide_password=False
    )
    pg_restore = str(Path(pg_dump).with_name("pg_restore"))
    try:
        _ = run(
            [pg_dump, "--format=custom", f"--file={partial}", f"--dbname={dsn}"],
            capture_output=True,
            check=True,
            env=environment,
        )
        _ = run(
            [pg_restore, "--list", str(partial)],
            capture_output=True,
            check=True,
        )
    except (OSError, CalledProcessError) as error:
        partial.unlink(missing_ok=True)
        stderr = getattr(error, "stderr", b"") or b""
        msg = f"backup failed: {stderr.decode(errors='replace').strip() or error}"
        raise BackupError(msg) from error
    _ = partial.rename(target)
    return target


def prune_backups(directory: Path, keep: int) -> list[Path]:
    """Delete all dumps but the newest ones.

    Args:
        directory: Path - Dump directory.
        keep: int - How many newest dumps to keep.

    Returns:
        list[Path] - The deleted dumps.

    """
    dumps = sorted(directory.glob("*.dump"), reverse=True)
    stale = dumps[keep:]
    for dump in stale:
        dump.unlink()
    return stale
