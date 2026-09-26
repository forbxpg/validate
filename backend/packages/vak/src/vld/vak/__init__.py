"""vld-vak: the VAK list of peer-reviewed journals as typed data.

The parse result lives in `vld.vak.models`, the parser in `vld.vak.parser`
(the `parser` extra).
"""

from __future__ import annotations

from .errors import NotVakListError, VakError
from .models import VakList

__all__ = ("NotVakListError", "VakError", "VakList")
