"""The parse result of one edition of the list: the JSON format, version 1."""

from __future__ import annotations

from datetime import date
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from ._journal import VakJournal
from ._warning import ParseWarning

FORMAT_VERSION = 1


class VakList(BaseModel):
    """One edition of the list as the parser read it.

    `model_dump_json()` writes the format and `model_validate_json()` reads it back;
    a document of another `format_version` is refused.

    Attributes:
        format_version: Literal[1] - Version of this format.
        parser_version: str - Version of vld-vak that produced it.
        edition_date: date - The «по состоянию на» date of page 1.
        page_count: int - Pages in the document.
        journals: tuple[VakJournal, ...] - Journals in number order.
        warnings: tuple[ParseWarning, ...] - Every warning of the document.

    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    format_version: Literal[1] = FORMAT_VERSION
    parser_version: str
    edition_date: date
    page_count: int
    journals: tuple[VakJournal, ...]
    warnings: tuple[ParseWarning, ...]
