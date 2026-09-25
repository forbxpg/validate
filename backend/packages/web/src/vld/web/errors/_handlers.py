"""Превращение исключений в единственную форму ответа об ошибке."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ._core_errors import (
    HTTP_SPEC,
    INTERNAL_SPEC,
    VALIDATION_SPEC,
)
from ._exc_info import db_error_kind, safe_exc_info
from ._request_id import REQUEST_ID_HEADER_NAME as REQUEST_ID_HEADER
from ._request_id import get_request_id
from ._response import ErrorDetail, ErrorResponse
from ._spec import ErrorSpec

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import Response

    from ._spec import ErrorRegistry


_INTERNAL_STATUS = 500
_INTERNAL_MESSAGE = "Внутренняя ошибка сервера."
_RETRY_AFTER_HEADER = "Retry-After"
_MAX_DETAIL_MESSAGE = 200
_NO_STORE = {"Cache-Control": "no-store"}


_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


def _render(
    request: Request,
    spec: ErrorSpec,
    exc: Exception,
    details: list[ErrorDetail] | None = None,
) -> Response:
    """Collect the response according to the error description.

    Args:
        request: Request - Request, from which the identifier is taken.
        spec: ErrorSpec - How the error looks outside.
        exc: Exception - The exception itself.
        details: list[ErrorDetail] | None - Claims to the request fields.

    Returns:
        Response - Response in a single form.

    """
    own_retry_after = getattr(exc, "retry_after", None)
    retry_after = (
        own_retry_after if isinstance(own_retry_after, int) else spec.retry_after
    )
    headers = dict(_NO_STORE)
    if retry_after is not None:
        headers[_RETRY_AFTER_HEADER] = str(retry_after)

    request_id = get_request_id(request)
    headers[REQUEST_ID_HEADER] = request_id
    emit = _log.error if spec.status >= _INTERNAL_STATUS else _log.info
    emit(
        "http_error_response",
        request_id=request_id,
        status=spec.status,
        code=str(spec.code),
        error=type(exc).__qualname__,
        db_error=db_error_kind(exc),
        exc_info=safe_exc_info(exc) if spec.status >= _INTERNAL_STATUS else None,
    )

    body = ErrorResponse(
        error=spec.code,
        message=spec.message,
        details=details,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=spec.status,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


def _make_handler(
    registry: ErrorRegistry,
) -> Callable[[Request, Exception], Awaitable[Response]]:
    """Collect the handler for one registry.

    Args:
        registry: ErrorRegistry - The table of errors of the module.

    Returns:
        The handler of exceptions in the form that starlette accepts.

    """

    async def _handle(request: Request, exc: Exception) -> Response:  # ruff: ignore[unused-async]
        """Send the response according to the table, and the unmapped error as 500.

        Args:
            request: Request - Request.
            exc: Exception - Caught exception.

        Returns:
            Response - Response in a single form.

        """
        spec = registry.mapping.get(type(exc))
        if spec is None:
            _log.error(
                "unmapped_error",
                error=type(exc).__qualname__,
                registry=registry.base.__qualname__,
                db_error=db_error_kind(exc),
                exc_info=safe_exc_info(exc),
            )
            spec = ErrorSpec(
                status=_INTERNAL_STATUS,
                code=registry.fallback_code,
                message=_INTERNAL_MESSAGE,
            )
        return _render(request, spec, exc)

    return _handle


async def _handle_validation(request: Request, exc: Exception) -> Response:  # ruff: ignore[unused-async]
    """Bring the validation error to the same form as the domain errors.

    Args:
        request: Request - Request.
        exc: Exception - Validation error.

    Returns:
        Response - Response in a single form.

    """
    details = (
        [
            ErrorDetail(
                field=".".join(
                    str(part) for part in cast("Sequence[object]", error["loc"])
                ),
                message=cast("str", error["msg"])[:_MAX_DETAIL_MESSAGE],
            )
            for error in cast("list[Mapping[str, object]]", exc.errors())
        ]
        if isinstance(exc, RequestValidationError)
        else None
    )
    return _render(request, VALIDATION_SPEC, exc, details)


async def _handle_http(request: Request, exc: Exception) -> Response:  # ruff: ignore[unused-async]
    """Bring the standard starlette responses (404, 405) to the same form.

    Args:
        request: Request - Request.
        exc: Exception - HTTP-level exception.

    Returns:
        Response - Response in a single form.

    """
    status = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
    headers = getattr(exc, "headers", None)
    retry_after = None
    if isinstance(headers, dict):
        raw = cast("dict[str, str]", headers).get(_RETRY_AFTER_HEADER)
        retry_after = int(raw) if raw is not None and raw.isdigit() else None
    return _render(
        request,
        ErrorSpec(
            status=status,
            code=HTTP_SPEC.code,
            message=HTTP_SPEC.message,
            retry_after=retry_after,
        ),
        exc,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> Response:  # ruff: ignore[unused-async]
    """The last line: everything that did not fit into any registry.

    Args:
        request: Request - Request.
        exc: Exception - Unhandled exception.

    Returns:
        Response - Response in a single form.

    """
    return _render(request, INTERNAL_SPEC, exc)


def register_error_handlers(app: FastAPI, *registries: ErrorRegistry) -> None:
    """Connect the error handlers to the application.

    Args:
        app: FastAPI - Application.
        registries: ErrorRegistry - Registries of errors of connected modules.

    """
    for registry in registries:
        app.add_exception_handler(registry.base, _make_handler(registry))
    app.add_exception_handler(RequestValidationError, _handle_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_http)
    app.add_exception_handler(Exception, _handle_unexpected)
