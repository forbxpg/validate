"""Finding and fetching the list on vak.gisnauka.ru: the `download` extra."""

from __future__ import annotations

from ._pdf import MAX_PDF_BYTES, VakPdf, fetch_pdf

__all__ = ("MAX_PDF_BYTES", "VakPdf", "fetch_pdf")
