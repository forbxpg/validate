"""Atomic mounting of the domain into the composite root."""

from __future__ import annotations

from ._descriptor import DomainDescriptor
from ._mount import mount

__all__ = ("DomainDescriptor", "mount")
