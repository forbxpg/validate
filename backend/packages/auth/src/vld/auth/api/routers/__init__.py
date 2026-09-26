"""HTTP endpoints of auth, one module per process."""

from __future__ import annotations

from ._common import ERROR_RESPONSES
from ._router import router

__all__ = ("ERROR_RESPONSES", "router")
