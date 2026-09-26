"""Warnings of a parse: everything doubtful, reported instead of dropped."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class WarningCode(StrEnum):
    """What a warning is about; the importer counts its thresholds by code.

    A code ending in ``_repaired`` marks a repair that was made; every other code
    marks something left as printed.
    """

    COLUMN_SHIFT = "column_shift"
    ROW_UNRECOGNIZED = "row_unrecognized"
    NUMBERING_GAP = "numbering_gap"
    TITLE_UNPARSED = "title_unparsed"
    TITLE_REPAIRED = "title_repaired"
    ISSN_MISSING = "issn_missing"
    ISSN_UNRECOGNIZED = "issn_unrecognized"
    ISSN_CHECKSUM = "issn_checksum"
    ISSN_REPAIRED = "issn_repaired"
    JOURNAL_WITHOUT_SPECIALITIES = "journal_without_specialities"
    SPECIALITY_UNRECOGNIZED = "speciality_unrecognized"
    BRANCH_MISSING = "branch_missing"
    BRANCH_UNKNOWN = "branch_unknown"
    BRANCH_REPAIRED = "branch_repaired"
    DATE_UNRECOGNIZED = "date_unrecognized"
    DATE_REPAIRED = "date_repaired"

    @property
    def is_repair(self) -> bool:
        """Whether the warning reports a repair that was made.

        Returns:
            bool - True for the ``_repaired`` codes.

        """
        return self.value.endswith("_repaired")


class ParseWarning(BaseModel):
    """One doubtful place of the document.

    Attributes:
        code: WarningCode - What it is about.
        page: int | None - Page, counting from 1; None for the whole document.
        number: int | None - Number of the journal it is about, if any.
        printed: str - The text concerned, as printed.
        message: str - Explanation in English.

    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    code: WarningCode
    page: int | None
    number: int | None
    printed: str
    message: str
