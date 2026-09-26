"""A journal of the list as printed: title, ISSNs, speciality groups with dates."""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from ._branch import ScienceBranch

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class Speciality(BaseModel):
    """One scientific speciality in one branch.

    Attributes:
        code: str - Code without a trailing dot or dash: ``5.9.5`` or ``10.02.01``.
        name: str - Name without the code and the branch bracket.
        branch: ScienceBranch | None - Branch; None when it could not be read.
        printed: str - The speciality as printed.

    """

    model_config: ClassVar[ConfigDict] = _FROZEN

    code: str
    name: str
    branch: ScienceBranch | None
    printed: str


class SpecialityGroup(BaseModel):
    """Specialities sharing one date cell: included together, excluded together.

    Attributes:
        dates_printed: str - The date cell as printed; empty when inherited.
        included: date | None - The «с» date.
        excluded: date | None - The «по» date; None while listed.
        specialities: tuple[Speciality, ...] - The specialities, in print order.

    """

    model_config: ClassVar[ConfigDict] = _FROZEN

    dates_printed: str
    included: date | None
    excluded: date | None
    specialities: tuple[Speciality, ...]


class FormerTitle(BaseModel):
    """A title the journal had in the list before a rename.

    Attributes:
        until: date | None - The date the title was used until, if printed.
        title: str - The former title.
        issns: tuple[str, ...] - Its ISSNs, normalized; empty if none were printed.

    """

    model_config: ClassVar[ConfigDict] = _FROZEN

    until: date | None
    title: str
    issns: tuple[str, ...]


class VakTitle(BaseModel):
    """The title cell taken apart.

    Attributes:
        printed: str - The cell verbatim, whitespace collapsed.
        main: str - The title without the brackets that were parsed.
        translation: str | None - The translation into Russian, if printed.
        former: tuple[FormerTitle, ...] - Former titles, in print order.

    """

    model_config: ClassVar[ConfigDict] = _FROZEN

    printed: str
    main: str
    translation: str | None
    former: tuple[FormerTitle, ...]


class VakJournal(BaseModel):
    """One numbered entry of the list.

    Attributes:
        number: int - The «№ п/п».
        pages: tuple[int, ...] - Pages the entry spans, counting from 1.
        title: VakTitle - The title cell.
        issn_printed: str - The ISSN cell as printed.
        issns: tuple[str, ...] - Normalized ISSNs ``NNNN-NNNC``, in print order.
        groups: tuple[SpecialityGroup, ...] - Speciality groups, in print order.

    """

    model_config: ClassVar[ConfigDict] = _FROZEN

    number: int
    pages: tuple[int, ...]
    title: VakTitle
    issn_printed: str
    issns: tuple[str, ...]
    groups: tuple[SpecialityGroup, ...]
