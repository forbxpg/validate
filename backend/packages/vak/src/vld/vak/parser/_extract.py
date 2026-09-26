"""Reading the PDF: rows of five cells with their page, the edition date, the bounds.

The only module that knows pdfplumber. Everything after it works on plain rows.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vld.vak.errors import NotVakListError

from ._dates import parse_day

try:
    import pdfplumber
    from pdfminer.psexceptions import PSException
    from pdfplumber.utils.exceptions import PdfminerException
except ModuleNotFoundError as error:
    _MISSING = (
        "vld.vak.parser requires the 'parser' extra: pip install 'vld-vak[parser]'"
    )
    raise ModuleNotFoundError(_MISSING, name=error.name) from error

if TYPE_CHECKING:
    from datetime import date

    from pdfplumber.page import Page

_EDITION_DATE = re.compile(r"по\s+состоянию\s+на\s+(\d{2}\.\d{2}\.\d{4})")
_HEADER_MARKS = ("Наименование издания", "ISSN")
# Rulings closer than this are one line drawn twice (x 34 and 35 on every page).
_SAME_LINE = 3.0
# A column ruling runs through the table; short rulings frame one cell.
_LONG_RULING = 0.5
_COLUMNS = 5
# The first pages are enough to find the bounds; a list without them is not a list.
_BOUND_SEARCH_PAGES = 3


@dataclass(frozen=True, slots=True)
class Row:
    """One table row, cells as pdfplumber read them, empty for a missing cell.

    Attributes:
        page: int - Page, counting from 1.
        number: str - The «№ п/п» cell.
        title: str - The title cell.
        issn: str - The ISSN cell.
        specialities: str - The specialities cell.
        dates: str - The date cell.

    """

    page: int
    number: str
    title: str
    issn: str
    specialities: str
    dates: str


@dataclass(frozen=True, slots=True)
class Extracted:
    """What the PDF gave before any interpretation.

    Attributes:
        edition_date: date - The «по состоянию на» date of page 1.
        page_count: int - Pages in the document.
        rows: tuple[Row, ...] - Table rows in page order, header rows left out.
        shifted_pages: tuple[int, ...] - Pages whose rulings differ from the bounds.

    """

    edition_date: date
    page_count: int
    rows: tuple[Row, ...]
    shifted_pages: tuple[int, ...]


def extract(data: bytes) -> Extracted:
    """Read the rows of every page with the column bounds of the document.

    Args:
        data: bytes - The PDF.

    Returns:
        Extracted - Rows, edition date, page count and pages with other rulings.

    Raises:
        NotVakListError: If the input is not a PDF, or has no header, no edition
            date or no column rulings.

    """
    if not data.startswith(b"%PDF-"):
        msg = "not a PDF: the data does not start with %PDF-"
        raise NotVakListError(msg)
    # pdfplumber reads lazily: a broken page fails on reading, not on opening.
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return _read(list(pdf.pages))
    except (PdfminerException, PSException) as error:
        msg = f"not a readable PDF: {error}"
        raise NotVakListError(msg) from error


def _read(pages: list[Page]) -> Extracted:
    if not pages:
        msg = "a PDF without pages"
        raise NotVakListError(msg)
    edition_date = _edition_date(pages[0])
    bounds = _document_bounds(pages)
    rows: list[Row] = []
    shifted: list[int] = []
    for index, page in enumerate(pages, start=1):
        if not _same_bounds(_long_rulings(page), bounds):
            shifted.append(index)
        rows.extend(_page_rows(page, index, bounds))
    return Extracted(
        edition_date=edition_date,
        page_count=len(pages),
        rows=tuple(rows),
        shifted_pages=tuple(shifted),
    )


def _edition_date(page: Page) -> date:
    text = page.extract_text() or ""
    if not all(mark in text for mark in _HEADER_MARKS):
        msg = "no table header on page 1"
        raise NotVakListError(msg)
    found = _EDITION_DATE.search(text)
    if found is None:
        msg = "no «по состоянию на» date on page 1"
        raise NotVakListError(msg)
    edition = parse_day(found.group(1))
    if edition is None:
        msg = f"the edition date {found.group(1)} is no date"
        raise NotVakListError(msg)
    return edition


def _document_bounds(pages: list[Page]) -> tuple[float, ...]:
    for page in pages[:_BOUND_SEARCH_PAGES]:
        bounds = _long_rulings(page)
        if len(bounds) == _COLUMNS + 1:
            return bounds
    msg = f"no page among the first {_BOUND_SEARCH_PAGES} has {_COLUMNS} columns"
    raise NotVakListError(msg)


def _long_rulings(page: Page) -> tuple[float, ...]:
    verticals = [
        (_coordinate(edge, "x0"), _coordinate(edge, "top"), _coordinate(edge, "bottom"))
        for edge in page.edges
        if edge["orientation"] == "v"
    ]
    if not verticals:
        return ()
    top = min(edge[1] for edge in verticals)
    bottom = max(edge[2] for edge in verticals)
    least = (bottom - top) * _LONG_RULING
    lengths: dict[float, float] = {}
    for x0, edge_top, edge_bottom in verticals:
        x = round(x0, 1)
        lengths[x] = lengths.get(x, 0.0) + edge_bottom - edge_top
    merged: list[float] = []
    for x in sorted(x for x, length in lengths.items() if length >= least):
        if merged and x - merged[-1] < _SAME_LINE:
            continue
        merged.append(x)
    return tuple(merged)


def _coordinate(edge: dict[str, object], key: str) -> float:
    value = edge[key]
    if not isinstance(value, int | float):
        msg = f"a ruling without a numeric {key}"
        raise NotVakListError(msg)
    return float(value)


def _same_bounds(found: tuple[float, ...], bounds: tuple[float, ...]) -> bool:
    return len(found) == len(bounds) and all(
        abs(a - b) < _SAME_LINE for a, b in zip(found, bounds, strict=True)
    )


def _page_rows(page: Page, index: int, bounds: tuple[float, ...]) -> list[Row]:
    settings = {
        "vertical_strategy": "explicit",
        "explicit_vertical_lines": list(bounds),
        "horizontal_strategy": "lines",
    }
    rows: list[Row] = []
    for table in page.extract_tables(settings):
        for cells in table:
            texts = [cell or "" for cell in cells]
            if len(texts) != _COLUMNS or _is_header(texts):
                continue
            rows.append(Row(index, *texts))
    return rows


def _is_header(cells: list[str]) -> bool:
    number, title, _, specialities, dates = (" ".join(cell.split()) for cell in cells)
    return (
        number.startswith("№")
        or title.startswith("Наименование издания")
        or specialities.startswith("Научные специальности")
        or dates.startswith("Дата включения")
    )
