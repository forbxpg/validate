"""What is not a VAK list is refused before anything is read."""

from __future__ import annotations

import io

import pypdf
import pytest
from pdfplumber.utils.exceptions import PdfminerException

from vld.vak.errors import NotVakListError
from vld.vak.parser import _extract, parse


def _blank_pdf(pages: int = 1) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        _ = writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    _ = writer.write(buffer)
    return buffer.getvalue()


def test_bytes_that_are_no_pdf_are_refused() -> None:
    """A page of HTML is no list."""
    with pytest.raises(NotVakListError, match="not a PDF"):
        parse(b"<html>404</html>")


def test_a_broken_pdf_is_refused() -> None:
    """A file that only starts like a PDF is no list."""
    with pytest.raises(NotVakListError, match="not a readable PDF"):
        parse(b"%PDF-1.5\n garbage")


def test_a_pdf_without_the_header_is_refused() -> None:
    """A PDF without the table header is no list."""
    with pytest.raises(NotVakListError, match="no table header"):
        parse(_blank_pdf())


def test_a_pdf_without_pages_is_refused() -> None:
    """An empty document is no list, not an index error."""
    with pytest.raises(NotVakListError, match="without pages"):
        parse(_blank_pdf(pages=0))


class _Page:
    def __init__(self, text: str) -> None:
        self._text: str = text

    def extract_text(self) -> str:
        return self._text


def test_an_edition_date_the_calendar_does_not_have_is_refused() -> None:
    """«по состоянию на 31.09.2026» is no date."""
    page = _Page("Наименование издания ISSN (по состоянию на 31.09.2026)")

    with pytest.raises(NotVakListError, match="edition date"):
        _extract._edition_date(page)  # pyright: ignore[reportArgumentType]


def test_a_pdf_that_breaks_after_opening_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken page tree or content stream is no list, not a pdfminer error."""

    def broken(_pages: object) -> object:
        message = "broken content stream"
        raise PdfminerException(message)

    monkeypatch.setattr(_extract, "_read", broken)

    with pytest.raises(NotVakListError, match="not a readable PDF"):
        parse(_blank_pdf())
