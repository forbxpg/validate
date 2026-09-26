"""Saved files: safe names, one document or records appended one by one."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from vld.crossref.cli._save import JsonLinesFile, file_name, write_json

if TYPE_CHECKING:
    from pathlib import Path

STAMP = datetime(2026, 9, 26, 14, 15, tzinfo=UTC)

pytestmark = pytest.mark.usefixtures("isolated")


def test_a_file_name_is_safe_for_any_file_system() -> None:
    """Slashes and odd characters of a DOI become underscores."""
    name = file_name(
        "works",
        "get",
        "10.1103/physrevlett.1.1",
        stamp=STAMP,
        suffix=".json",
    )

    assert name == "works-get-10.1103_physrevlett.1.1-20260926T141500.json"


def test_a_document_is_written_into_a_new_folder(tmp_path: Path) -> None:
    """The folder is created when missing."""
    path = tmp_path / "a" / "b" / "doc.json"

    write_json(path, {"DOI": "10.1/x"})

    assert json.loads(path.read_text()) == {"DOI": "10.1/x"}


def test_json_lines_are_on_disk_before_the_file_closes(tmp_path: Path) -> None:
    """Each record is flushed, so an interrupted walk keeps it."""
    path = tmp_path / "walk.jsonl"

    with JsonLinesFile(path) as saving:
        saving.write({"n": 1})
        saving.write({"n": 2})
        on_disk = path.read_text().splitlines()

    assert [json.loads(line) for line in on_disk] == [{"n": 1}, {"n": 2}]
    assert saving.count == 2


def test_a_second_walk_into_the_same_file_replaces_it(tmp_path: Path) -> None:
    """Records of two runs must not mix in one file."""
    path = tmp_path / "walk.jsonl"
    for run in (1, 2):
        with JsonLinesFile(path) as saving:
            saving.write({"run": run})

    assert path.read_text().splitlines() == ['{"run": 2}']
