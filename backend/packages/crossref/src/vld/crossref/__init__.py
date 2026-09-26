"""Asynchronous typed client of the Crossref REST API."""

from __future__ import annotations

from ._client import CrossrefClient
from .errors import (
    CrossrefBadRequestError,
    CrossrefBlockedError,
    CrossrefCursorExpiredError,
    CrossrefError,
    CrossrefQueryError,
    CrossrefRateLimitedError,
    CrossrefSchemaError,
    CrossrefUnavailableError,
    ValidationProblem,
)
from .ids import normalize_doi, normalize_issn
from .models import PartialDate
from .throttle import LocalThrottle, RateLimits, Throttle
from .transport import RetryPolicy

__all__ = (
    "CrossrefBadRequestError",
    "CrossrefBlockedError",
    "CrossrefClient",
    "CrossrefCursorExpiredError",
    "CrossrefError",
    "CrossrefQueryError",
    "CrossrefRateLimitedError",
    "CrossrefSchemaError",
    "CrossrefUnavailableError",
    "LocalThrottle",
    "PartialDate",
    "RateLimits",
    "RetryPolicy",
    "Throttle",
    "ValidationProblem",
    "normalize_doi",
    "normalize_issn",
)
