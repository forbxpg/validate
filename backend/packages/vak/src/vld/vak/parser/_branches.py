"""Reading the branch bracket of a speciality through a closed table."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vld.vak.models import ScienceBranch, WarningCode

from ._finding import Finding

# How the list prints each branch when it prints it right.
CANONICAL: dict[ScienceBranch, str] = {
    ScienceBranch.AGRICULTURE: "сельскохозяйственные науки",
    ScienceBranch.ARCHITECTURE: "архитектура",
    ScienceBranch.ART_HISTORY: "искусствоведение",
    ScienceBranch.BIOLOGY: "биологические науки",
    ScienceBranch.CHEMISTRY: "химические науки",
    ScienceBranch.CULTURAL_STUDIES: "культурология",
    ScienceBranch.ECONOMICS: "экономические науки",
    ScienceBranch.GEOGRAPHY: "географические науки",
    ScienceBranch.GEOLOGY_MINERALOGY: "геолого-минералогические науки",
    ScienceBranch.HISTORY: "исторические науки",
    ScienceBranch.LAW: "юридические науки",
    ScienceBranch.MEDICINE: "медицинские науки",
    ScienceBranch.MILITARY: "военные науки",
    ScienceBranch.PEDAGOGY: "педагогические науки",
    ScienceBranch.PHARMACY: "фармацевтические науки",
    ScienceBranch.PHILOLOGY: "филологические науки",
    ScienceBranch.PHILOSOPHY: "философские науки",
    ScienceBranch.PHYSICS_MATHEMATICS: "физико-математические науки",
    ScienceBranch.POLITICAL_SCIENCE: "политические науки",
    ScienceBranch.PSYCHOLOGY: "психологические науки",
    ScienceBranch.SOCIOLOGY: "социологические науки",
    ScienceBranch.TECHNICAL: "технические науки",
    ScienceBranch.THEOLOGY: "теология",
    ScienceBranch.VETERINARY: "ветеринарные науки",
}

# Misprints seen in the list, each read as one branch. A new one is a warning
# until it is added here with its test.
SYNONYMS: dict[str, ScienceBranch] = {
    "культурологические": ScienceBranch.CULTURAL_STUDIES,
    "технически": ScienceBranch.TECHNICAL,
}

_SCIENCES = re.compile(r"наук[аи]?$")


@dataclass(frozen=True, slots=True)
class BranchReading:
    """The branches of one bracket.

    Attributes:
        branches: tuple[ScienceBranch, ...] - One branch, or several when the
            bracket lists several; empty when nothing was read.
        finding: Finding | None - A repair or a failure to read.

    """

    branches: tuple[ScienceBranch, ...]
    finding: Finding | None


def read_branches(bracket: str) -> BranchReading:
    """Read the inside of a branch bracket.

    Args:
        bracket: str - The text inside the brackets, as printed.

    Returns:
        BranchReading - The branches and what was repaired or not understood.

    """
    parts = [part for part in re.split(r"[,;]", bracket) if part.strip()]
    branches: list[ScienceBranch] = []
    for part in parts:
        branch = _branch(part)
        if branch is None:
            return BranchReading(
                (),
                Finding(
                    WarningCode.BRANCH_UNKNOWN,
                    bracket,
                    f"not a branch: {part.strip()!r}",
                ),
            )
        branches.append(branch)
    if not branches:
        return BranchReading(
            (),
            Finding(WarningCode.BRANCH_MISSING, bracket, "empty branch"),
        )
    if len(branches) == 1 and bracket == CANONICAL[branches[0]]:
        return BranchReading((branches[0],), None)
    shown = ", ".join(CANONICAL[branch] for branch in branches)
    return BranchReading(
        tuple(branches),
        Finding(WarningCode.BRANCH_REPAIRED, bracket, f"read as {shown!r}"),
    )


def branch_of_name(name: str) -> ScienceBranch | None:
    """Tell whether a whole speciality name is a branch, as «6.0.0 Военные науки».

    Args:
        name: str - The speciality name.

    Returns:
        ScienceBranch | None - The branch the name spells, if it spells one.

    """
    return _branch(name)


def _branch(text: str) -> ScienceBranch | None:
    key = _SCIENCES.sub("", re.sub(r"\s+", "", text.lower()).strip(".")).strip()
    for branch, printed in CANONICAL.items():
        if key == _SCIENCES.sub("", printed.replace(" ", "")):
            return branch
    return SYNONYMS.get(key)
