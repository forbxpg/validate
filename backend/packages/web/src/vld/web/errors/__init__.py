"""Single form of the HTTP response error and its delivery mechanism."""

from __future__ import annotations

from ._common_responses import COMMON_ERROR_RESPONSES
from ._core_errors import CORE_ERRORS, CoreErrorCode
from ._exc_info import db_error_kind, safe_exc_info
from ._handlers import register_error_handlers
from ._request_id import (
    REQUEST_ID_HEADER_NAME,
    RequestIdMiddleware,
    get_request_id,
)
from ._response import ErrorDetail, ErrorResponse
from ._spec import ErrorRegistry, ErrorSpec

__all__ = (
    "COMMON_ERROR_RESPONSES",
    "CORE_ERRORS",
    "REQUEST_ID_HEADER_NAME",
    "CoreErrorCode",
    "ErrorDetail",
    "ErrorRegistry",
    "ErrorResponse",
    "ErrorSpec",
    "RequestIdMiddleware",
    "db_error_kind",
    "get_request_id",
    "register_error_handlers",
    "safe_exc_info",
)
