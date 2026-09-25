"""Pagination contracts that stay free of the HTTP layer."""

from __future__ import annotations

from ._projection import Projection
from ._protocols import Page, PageParams
from ._transformer import transformer

__all__ = ("Page", "PageParams", "Projection", "transformer")
