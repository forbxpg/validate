"""The journals routes: resource, query and model."""

from __future__ import annotations

from ._model import Journal, JournalCounts, JournalIssn
from ._query import JournalsQuery
from ._resource import JournalsResource

__all__ = (
    "Journal",
    "JournalCounts",
    "JournalIssn",
    "JournalsQuery",
    "JournalsResource",
)
