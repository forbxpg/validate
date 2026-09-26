"""HTTP to Crossref: identity, one request with limits and retries, the envelope."""

from __future__ import annotations

from ._envelope import Envelope
from ._identity import VERSION, Identity
from ._request import BASE_URL, Transport
from ._retry import (
    DEFAULT_RETRY,
    RetryPolicy,
    TransientFailure,
    retry_after_seconds,
    wait_seconds,
)

__all__ = (
    "BASE_URL",
    "DEFAULT_RETRY",
    "VERSION",
    "Envelope",
    "Identity",
    "RetryPolicy",
    "TransientFailure",
    "Transport",
    "retry_after_seconds",
    "wait_seconds",
)
