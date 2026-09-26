"""The limits Crossref reports in the headers of every response."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING

import structlog

from ._port import RateLimits

if TYPE_CHECKING:
    from collections.abc import Mapping

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger("vld.crossref")

_INTERVAL = re.compile(r"(\d+)(ms|s|m)")
_UNITS = {"ms": "milliseconds", "s": "seconds", "m": "minutes"}
_warned: set[str] = set()


def _interval(raw: str) -> timedelta | None:
    match = _INTERVAL.fullmatch(raw.strip())
    if match is None:
        return None
    return timedelta(**{_UNITS[match.group(2)]: int(match.group(1))})


def parse_limits(headers: Mapping[str, str]) -> RateLimits | None:
    """Read the limits from the headers of a response.

    Missing headers give None silently; malformed ones give None and one warning
    per distinct value.

    Args:
        headers: Mapping[str, str] - Headers of the response, keys in lower case
            or a case-insensitive mapping.

    Returns:
        RateLimits | None - The limits, or None when they cannot be read.

    """
    limit = headers.get("x-rate-limit-limit")
    interval = headers.get("x-rate-limit-interval")
    if limit is None or interval is None:
        return None
    concurrency = headers.get("x-concurrency-limit")
    pool = headers.get("x-api-pool")
    span = _interval(interval)
    numbers = _ints(limit, concurrency)
    if span is None or numbers is None:
        _warn_once(f"{limit}/{interval}/{concurrency}")
        return None
    requests, parallel = numbers
    try:
        return RateLimits(requests, span, parallel, pool)
    except ValueError:
        _warn_once(f"{limit}/{interval}/{concurrency}")
        return None


def _ints(limit: str, concurrency: str | None) -> tuple[int, int | None] | None:
    try:
        return int(limit), None if concurrency is None else int(concurrency)
    except ValueError:
        return None


def _warn_once(raw: str) -> None:
    if raw not in _warned:
        _warned.add(raw)
        _log.warning("crossref_limits_unreadable", raw=raw)
