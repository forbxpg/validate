"""The parse result of the VAK list: format v1, pydantic only."""

from __future__ import annotations

from ._branch import ScienceBranch
from ._journal import FormerTitle, Speciality, SpecialityGroup, VakJournal, VakTitle
from ._list import FORMAT_VERSION, VakList
from ._warning import ParseWarning, WarningCode

__all__ = (
    "FORMAT_VERSION",
    "FormerTitle",
    "ParseWarning",
    "ScienceBranch",
    "Speciality",
    "SpecialityGroup",
    "VakJournal",
    "VakList",
    "VakTitle",
    "WarningCode",
)
