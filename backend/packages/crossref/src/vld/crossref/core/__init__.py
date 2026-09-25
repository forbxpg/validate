"""Building blocks of the Crossref client: errors and the retry policy."""

from __future__ import annotations

from ._decorators import TRANSIENT_ERRORS, retry
from ._errors import (
    CrossrefAPIError,
    CrossrefClientError,
    CrossrefMaxOffsetError,
    CrossrefNotFoundError,
    CrossrefRateLimitError,
    CrossrefRequestTimeoutError,
    CrossrefServerError,
    CrossrefUrlSyntaxError,
)

__all__ = (
    "TRANSIENT_ERRORS",
    "CrossrefAPIError",
    "CrossrefClientError",
    "CrossrefMaxOffsetError",
    "CrossrefNotFoundError",
    "CrossrefRateLimitError",
    "CrossrefRequestTimeoutError",
    "CrossrefServerError",
    "CrossrefUrlSyntaxError",
    "retry",
)
