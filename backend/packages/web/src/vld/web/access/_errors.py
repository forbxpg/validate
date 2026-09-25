"""Access refusals, which are produced by the mechanism itself, not the domain."""

from __future__ import annotations

from http import HTTPStatus

from vld.web.errors import CoreErrorCode, ErrorRegistry, ErrorResponse, ErrorSpec


class AccessError(Exception):
    """Common parent of access refusals."""


class NotAuthenticatedError(AccessError):
    """The token is not presented or presented not in the `Bearer <token>` form."""


class AccessDeniedError(AccessError):
    """The token is valid, but the role is not in the number of allowed."""


class UnmarkedRouteError(Exception):
    """The route is mounted without the access marker."""


ACCESS_ERRORS = ErrorRegistry(
    base=AccessError,
    mapping={
        NotAuthenticatedError: ErrorSpec(
            status=HTTPStatus.UNAUTHORIZED,
            code=CoreErrorCode.NOT_AUTHENTICATED,
            message="Требуется вход.",
        ),
        AccessDeniedError: ErrorSpec(
            status=HTTPStatus.FORBIDDEN,
            code=CoreErrorCode.ACCESS_DENIED,
            message="Недостаточно прав.",
        ),
    },
    fallback_code=CoreErrorCode.INTERNAL_ERROR,
)

PROTECTED_ERROR_RESPONSES: dict[
    int | str,
    dict[
        str,
        type[ErrorResponse],
    ],
] = {
    HTTPStatus.UNAUTHORIZED: {
        "model": ErrorResponse,
    },
    HTTPStatus.FORBIDDEN: {
        "model": ErrorResponse,
    },
}
