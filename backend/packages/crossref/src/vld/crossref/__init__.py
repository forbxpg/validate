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
from .pagination import (
    CURSOR_LIFETIME,
    MAX_OFFSET_WINDOW,
    MAX_ROWS,
    Facet,
    FacetValue,
    Page,
    check_page,
    check_walk,
    page_from_message,
    parse_facets,
    read_items,
    walk,
)
from .throttle import LocalThrottle, RateLimits, Throttle
from .transport import RetryPolicy

__all__ = (
    "CURSOR_LIFETIME",
    "MAX_OFFSET_WINDOW",
    "MAX_ROWS",
    "CrossrefBadRequestError",
    "CrossrefBlockedError",
    "CrossrefClient",
    "CrossrefCursorExpiredError",
    "CrossrefError",
    "CrossrefQueryError",
    "CrossrefRateLimitedError",
    "CrossrefSchemaError",
    "CrossrefUnavailableError",
    "Facet",
    "FacetValue",
    "LocalThrottle",
    "Page",
    "PartialDate",
    "RateLimits",
    "RetryPolicy",
    "Throttle",
    "ValidationProblem",
    "check_page",
    "check_walk",
    "normalize_doi",
    "normalize_issn",
    "page_from_message",
    "parse_facets",
    "read_items",
    "walk",
)
