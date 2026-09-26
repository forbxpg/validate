"""A finding of a cell reader, before the page and journal number are known."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vld.vak.models import WarningCode


@dataclass(frozen=True, slots=True)
class Finding:
    """Something doubtful in one cell; the assembler turns it into a warning.

    Attributes:
        code: WarningCode - What it is about.
        printed: str - The text concerned.
        message: str - Explanation in English.

    """

    code: WarningCode
    printed: str
    message: str


def flatten(text: str) -> str:
    """Join the lines of a cell into one line.

    A hyphen at the end of a line joins its word with the next line without a
    space: that is how a cell wraps «физико-математические». A hyphen followed by
    a space inside a line is left alone: that is a misprint for the readers to
    report.

    Args:
        text: str - The cell as pdfplumber read it.

    Returns:
        str - One line, whitespace collapsed.

    """
    joined = re.sub(r"-\n\s*", "-", text)
    return re.sub(r"\s+", " ", joined).strip()
