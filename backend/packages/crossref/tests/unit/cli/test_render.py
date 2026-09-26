"""What a person sees: smoke tests on a terminal console, no snapshots."""

from __future__ import annotations

import io
from typing import cast

import pytest
from crossref_support import fixture
from rich.console import Console

from vld.crossref.cli._render import summary, work_panel, works_table
from vld.crossref.works._list import parse_work

pytestmark = pytest.mark.usefixtures("isolated")


def _work():
    message = cast("dict[str, object]", fixture("work_journal_article"))["message"]
    work = parse_work(message)
    assert work is not None
    return work


def _printed(renderable: object) -> str:
    buffer = io.StringIO()
    Console(file=buffer, force_terminal=True, width=140, color_system=None).print(
        renderable,
    )
    return buffer.getvalue()


def test_the_card_of_a_work_shows_its_title_doi_and_journal() -> None:
    """The fields a person looks for first."""
    printed = _printed(work_panel(_work()))

    assert "Editorial" in printed
    assert "10.1103/physrevlett.1.1" in printed
    assert "Physical Review Letters" in printed


def test_a_table_row_per_work() -> None:
    """DOI and year in the row."""
    printed = _printed(works_table([_work(), _work()]))

    assert printed.count("10.1103/physrevlett.1.1") == 2
    assert "1958" in printed


def test_the_summary_says_how_much_and_which_pool() -> None:
    """Thousands are separated for reading."""
    assert summary(shown=20, total=1234567, offset=0, pool="polite") == (
        "20 of 1 234 567 · pool: polite"
    )
    assert (
        summary(shown=5, total=None, offset=40, pool=None)
        == "5 · from 40 · pool: unknown"
    )
