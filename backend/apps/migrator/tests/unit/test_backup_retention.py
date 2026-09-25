"""Dump retention keeps the newest dumps and leaves unfinished ones alone."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.migrator._backup import prune_backups

if TYPE_CHECKING:
    from pathlib import Path


def test_prune_keeps_the_newest_dumps(tmp_path: Path) -> None:
    """Dump names start with a UTC timestamp, so name order is age order."""
    names = [f"2026092{day}T000000Z-r1.dump" for day in range(1, 8)]
    for name in names:
        _ = (tmp_path / name).write_bytes(b"")
    _ = (tmp_path / "20260930T000000Z-r2.partial").write_bytes(b"")

    removed = prune_backups(tmp_path, keep=5)

    assert sorted(path.name for path in removed) == names[:2]
    assert sorted(path.name for path in tmp_path.glob("*.dump")) == names[2:]
    assert (tmp_path / "20260930T000000Z-r2.partial").exists()
