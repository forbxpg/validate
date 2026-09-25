"""Statuses that any mounted router may return."""

from __future__ import annotations

from http import HTTPStatus

from ._response import ErrorResponse

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, type[ErrorResponse]]] = {
    HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    HTTPStatus.TOO_MANY_REQUESTS: {"model": ErrorResponse},
    HTTPStatus.INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    HTTPStatus.BAD_GATEWAY: {"model": ErrorResponse},
    HTTPStatus.SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}
