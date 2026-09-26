"""The entry point of the parser: the bytes of a PDF into a `VakList`."""

from __future__ import annotations

from importlib.metadata import version

from vld.vak.models import ParseWarning, VakList, WarningCode

from ._assemble import assemble
from ._extract import extract


def parse(data: bytes) -> VakList:
    """Read one edition of the VAK list.

    Synchronous and CPU bound, about a minute for the whole list: an async caller
    runs it in a thread. Nothing is dropped: every doubtful place is a warning.

    Args:
        data: bytes - The PDF.

    Returns:
        VakList - The edition as read, with its warnings.

    """
    extracted = extract(data)
    assembled = assemble(extracted.rows)
    shifts = tuple(
        ParseWarning(
            code=WarningCode.COLUMN_SHIFT,
            page=page,
            number=None,
            printed="",
            message="the column rulings of the page differ from the document's",
        )
        for page in extracted.shifted_pages
    )
    unaligned = tuple(
        ParseWarning(
            code=WarningCode.ROW_UNRECOGNIZED,
            page=page,
            number=None,
            printed=printed,
            message="a row not five cells wide",
        )
        for page, printed in extracted.unaligned
    )
    return VakList(
        parser_version=version("vld-vak"),
        edition_date=extracted.edition_date,
        page_count=extracted.page_count,
        journals=assembled.journals,
        warnings=shifts + unaligned + assembled.warnings,
    )
