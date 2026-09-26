"""A whole edition, by hand: `VAK_PDF_PATH=/path/to/list.pdf uv run pytest -m vak_full`.

About a minute. Run it before releasing a new version of the parser.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import pytest

from vld.vak.models import VakList, WarningCode
from vld.vak.parser import parse

pytestmark = pytest.mark.vak_full

# The share of journals with a warning that is not a repair. The editions of
# 30.03.2026 and 15.09.2026 stay under 1 %.
MOST_DOUBTFUL = 0.02


@cache
def _list() -> VakList:
    path = os.environ.get("VAK_PDF_PATH")
    if not path:
        pytest.skip("VAK_PDF_PATH is not set")
    return parse(Path(path).read_bytes())


def test_the_numbers_run_from_one_without_gaps() -> None:
    """No journal is lost or read twice."""
    numbers = [journal.number for journal in _list().journals]

    assert numbers == list(range(1, len(numbers) + 1))


def test_no_row_is_left_unrecognized_after_the_header() -> None:
    """Every row belongs to a journal or to the header."""
    unrecognized = [
        warning
        for warning in _list().warnings
        if warning.code is WarningCode.ROW_UNRECOGNIZED
    ]

    assert unrecognized == []


def test_few_journals_carry_a_doubt() -> None:
    """Journals with a warning other than a repair stay rare."""
    doubtful = {
        warning.number
        for warning in _list().warnings
        if warning.number is not None and not warning.code.is_repair
    }

    assert len(doubtful) / len(_list().journals) < MOST_DOUBTFUL
