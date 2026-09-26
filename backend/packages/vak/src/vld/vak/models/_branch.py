"""Science branches of the nomenclature of scientific specialities."""

from __future__ import annotations

from enum import StrEnum


class ScienceBranch(StrEnum):
    """A branch of science a degree is awarded in: the bracket after a speciality.

    A closed list: a branch the list prints but this enum lacks is reported by the
    parser, never added on the fly.
    """

    AGRICULTURE = "agriculture"
    ARCHITECTURE = "architecture"
    ART_HISTORY = "art_history"
    BIOLOGY = "biology"
    CHEMISTRY = "chemistry"
    CULTURAL_STUDIES = "cultural_studies"
    ECONOMICS = "economics"
    GEOGRAPHY = "geography"
    GEOLOGY_MINERALOGY = "geology_mineralogy"
    HISTORY = "history"
    LAW = "law"
    MEDICINE = "medicine"
    MILITARY = "military"
    PEDAGOGY = "pedagogy"
    PHARMACY = "pharmacy"
    PHILOLOGY = "philology"
    PHILOSOPHY = "philosophy"
    PHYSICS_MATHEMATICS = "physics_mathematics"
    POLITICAL_SCIENCE = "political_science"
    PSYCHOLOGY = "psychology"
    SOCIOLOGY = "sociology"
    TECHNICAL = "technical"
    THEOLOGY = "theology"
    VETERINARY = "veterinary"
