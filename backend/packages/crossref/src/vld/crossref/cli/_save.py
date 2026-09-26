"""Saved results: file names, one JSON document or JSON Lines as a walk goes."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path
    from types import TracebackType
    from typing import IO

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_STAMP = "%Y%m%dT%H%M%S"


def file_name(*parts: str, stamp: datetime, suffix: str) -> str:
    """Name a saved file: its parts, safe for any file system, and the time.

    Args:
        *parts: str - Resource, command and what was asked (a DOI, a fingerprint).
        stamp: datetime - When the command ran.
        suffix: str - `.json` or `.jsonl`.

    Returns:
        str - Such as `works-get-10.1103_physrevlett.1.1-20260926T141500.json`.

    """
    safe = [_UNSAFE.sub("_", part).strip("_") for part in parts if part]
    return "-".join([*safe, stamp.strftime(_STAMP)]) + suffix


def write_json(path: Path, document: object) -> None:
    """Write one JSON document, creating the folder when missing.

    Args:
        path: Path - The file.
        document: object - JSON-ready data.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class JsonLinesFile:
    """A JSON Lines file written record by record and flushed each time.

    An interrupted walk leaves every record received so far.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        self.count: int = 0
        self._file: IO[str] | None = None

    def __enter__(self) -> Self:
        """Open the file, replacing an earlier one of the same name.

        Returns:
            Self - The writer.

        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")
        return self

    def write(self, record: object) -> None:
        """Append one record and flush it to disk.

        Args:
            record: object - JSON-ready data.

        Raises:
            RuntimeError: If the file is not open.

        """
        if self._file is None:
            msg = "use JsonLinesFile in a with block"
            raise RuntimeError(msg)
        _ = self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()
        self.count += 1

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the file.

        Args:
            exc_type: type[BaseException] | None - Type of the error, if any.
            exc: BaseException | None - The error, if any.
            tb: TracebackType | None - Its traceback, if any.

        """
        del exc_type, exc, tb
        if self._file is not None:
            self._file.close()
            self._file = None
