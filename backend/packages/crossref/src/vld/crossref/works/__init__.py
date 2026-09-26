"""The works routes: resource, list, query and model."""

from __future__ import annotations

from ._list import WorkList
from ._resource import WorksResource

__all__ = ("WorkList", "WorksResource")
