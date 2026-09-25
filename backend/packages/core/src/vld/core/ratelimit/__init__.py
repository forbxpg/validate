"""Ограничение частоты запросов."""

from __future__ import annotations

from ._redis_limiter import (
    RateLimiter,
    RateLimiterUnavailableError,
    RateLimitExceededError,
)

__all__ = (
    "RateLimitExceededError",
    "RateLimiter",
    "RateLimiterUnavailableError",
)
