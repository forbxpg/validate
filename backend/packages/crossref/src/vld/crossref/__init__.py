"""Asynchronous typed client of the Crossref REST API."""

from __future__ import annotations

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

__all__ = (
    "CrossrefBadRequestError",
    "CrossrefBlockedError",
    "CrossrefCursorExpiredError",
    "CrossrefError",
    "CrossrefQueryError",
    "CrossrefRateLimitedError",
    "CrossrefSchemaError",
    "CrossrefUnavailableError",
    "PartialDate",
    "ValidationProblem",
    "normalize_doi",
    "normalize_issn",
)
