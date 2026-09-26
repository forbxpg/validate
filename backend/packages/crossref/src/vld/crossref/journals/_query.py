"""A journals query: the route takes text and nothing else."""

from __future__ import annotations

from typing import override

from vld.crossref.models import QueryModel, Text


class JournalsQuery(QueryModel):
    """What to look for among journals.

    Crossref refuses filters, field queries, sort, select and facets on
    ``/journals``; a parameter it adds later becomes a field here.

    Attributes:
        text: str | None - Free text (``query``).

    """

    text: Text = None

    @override
    def params(self) -> dict[str, str]:
        """Render the query into Crossref parameters.

        Returns:
            dict[str, str] - The parameters; empty for an empty query.

        """
        return {} if self.text is None else {"query": self.text}
