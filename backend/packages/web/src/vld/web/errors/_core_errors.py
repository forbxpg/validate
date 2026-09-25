"""Registry of the errors that come from `vld.core`."""

from __future__ import annotations

from enum import StrEnum

from vld.core.ratelimit import (
    RateLimiterUnavailableError,
    RateLimitExceededError,
)

from ._spec import ErrorRegistry, ErrorSpec


class CoreErrorCode(StrEnum):
    """Error codes of the infrastructure layer."""

    ACCESS_DENIED = "core.access_denied"
    HTTP_ERROR = "core.http_error"
    INTERNAL_ERROR = "core.internal_error"
    NOT_AUTHENTICATED = "core.not_authenticated"
    RATE_LIMIT_EXCEEDED = "core.rate_limit_exceeded"
    VALIDATION_FAILED = "core.validation_failed"


HTTP_SPEC = ErrorSpec(
    status=400,
    code=CoreErrorCode.HTTP_ERROR,
    message="Запрос не может быть выполнен.",
)

INTERNAL_SPEC = ErrorSpec(
    status=500,
    code=CoreErrorCode.INTERNAL_ERROR,
    message="Внутренняя ошибка сервера.",
)

VALIDATION_SPEC = ErrorSpec(
    status=422,
    code=CoreErrorCode.VALIDATION_FAILED,
    message="Запрос не прошёл проверку.",
)

_RATE_LIMIT_SPEC = ErrorSpec(
    status=429,
    code=CoreErrorCode.RATE_LIMIT_EXCEEDED,
    message="Слишком много попыток. Повторите позже.",
)

CORE_ERRORS = ErrorRegistry(
    base=RateLimitExceededError,
    mapping={
        RateLimitExceededError: _RATE_LIMIT_SPEC,
        RateLimiterUnavailableError: _RATE_LIMIT_SPEC,
    },
    fallback_code=CoreErrorCode.INTERNAL_ERROR,
)
