"""What is not a VAK list is refused before anything is read."""

from __future__ import annotations

import io

import pypdf
import pytest

from vld.vak.errors import NotVakListError
from vld.vak.parser import parse


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
