"""Limits of Crossref: the port, the one-process implementation, the headers."""

from __future__ import annotations

from ._headers import parse_limits
from ._local import LocalThrottle
from ._port import RateLimits, Throttle

__all__ = ("LocalThrottle", "RateLimits", "Throttle", "parse_limits")
