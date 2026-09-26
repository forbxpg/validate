"""Errors of the Crossref client."""

from __future__ import annotations

from ._errors import (
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

__all__ = (
    "CrossrefBadRequestError",
    "CrossrefBlockedError",
    "CrossrefCursorExpiredError",
    "CrossrefError",
    "CrossrefQueryError",
    "CrossrefRateLimitedError",
    "CrossrefSchemaError",
    "CrossrefUnavailableError",
    "ValidationProblem",
)
