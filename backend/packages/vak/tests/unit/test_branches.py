"""Branch brackets: the closed table, its synonyms, and what is not a branch."""

from __future__ import annotations

import pytest

from vld.vak.models import ScienceBranch, WarningCode
from vld.vak.parser._branches import (
    CANONICAL,
    SYNONYMS,
    BranchReading,
    branch_of_name,
    read_branches,
)


def test_every_branch_has_its_printed_form() -> None:
    """The table covers the whole closed list."""
    assert set(CANONICAL) == set(ScienceBranch)


@pytest.mark.parametrize(("branch", "printed"), list(CANONICAL.items()))
def test_a_canonical_bracket_is_read_without_a_finding(
    branch: ScienceBranch,
    printed: str,
) -> None:
    """Each branch printed right is read without a warning."""
    assert read_branches(printed) == BranchReading((branch,), None)


@pytest.mark.parametrize(("printed", "branch"), list(SYNONYMS.items()))
def test_every_synonym_is_read_and_reported(
    printed: str,
    branch: ScienceBranch,
) -> None:
    """Each synonym of the table is read and reported as a repair."""
    reading = read_branches(printed)

    assert reading.branches == (branch,)
    assert reading.finding is not None
    assert reading.finding.code is WarningCode.BRANCH_REPAIRED


@pytest.mark.parametrize(
    ("printed", "branch"),
    [
        ("Фармацевтические науки", ScienceBranch.PHARMACY),
        ("юридические науки,", ScienceBranch.LAW),
        (" экономические науки", ScienceBranch.ECONOMICS),
        ("техническиенауки", ScienceBranch.TECHNICAL),
        ("геолого-минералогические", ScienceBranch.GEOLOGY_MINERALOGY),
        ("культурология науки", ScienceBranch.CULTURAL_STUDIES),
        ("культурологические", ScienceBranch.CULTURAL_STUDIES),
        ("технически науки", ScienceBranch.TECHNICAL),
    ],
)
def test_a_misprinted_bracket_is_read_and_reported(
    printed: str,
    branch: ScienceBranch,
) -> None:
    """Case, spacing and a missing «науки» are repairs."""
    reading = read_branches(printed)

    assert reading.branches == (branch,)
    assert reading.finding is not None
    assert reading.finding.code is WarningCode.BRANCH_REPAIRED


def test_two_branches_in_one_bracket_are_both_read() -> None:
    """«(философские науки, исторические науки)» is two branches."""
    reading = read_branches("философские науки, исторические науки")

    assert reading.branches == (ScienceBranch.PHILOSOPHY, ScienceBranch.HISTORY)
    assert reading.finding is not None
    assert reading.finding.code is WarningCode.BRANCH_REPAIRED


@pytest.mark.parametrize(
    "printed",
    ["технические системы", "государственно-правовые", "медицинские е науки"],
)
def test_what_is_no_branch_is_reported_and_read_as_none(printed: str) -> None:
    """An unknown bracket never becomes a new branch."""
    reading = read_branches(printed)

    assert reading.branches == ()
    assert reading.finding is not None
    assert reading.finding.code is WarningCode.BRANCH_UNKNOWN


def test_a_name_that_spells_a_branch_is_that_branch() -> None:
    """«военные науки» as a whole speciality is the military branch."""
    assert branch_of_name("военные науки") is ScienceBranch.MILITARY
    assert branch_of_name("Кардиология") is None


def test_an_empty_bracket_is_a_missing_branch() -> None:
    """«Кардиология ()» names no branch."""
    reading = read_branches("")

    assert reading.branches == ()
    assert reading.finding is not None
    assert reading.finding.code is WarningCode.BRANCH_MISSING
