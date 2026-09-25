"""The body of the error response — the only form in the entire API."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """One claim to one request field.

    Attributes:
        field: str - The path to the request field, dots (``body.email``).
        message: str - What's wrong with it.

    """

    field: str
    message: str


class ErrorResponse(BaseModel):
    """The error response.

    Attributes:
        error: str - Machine code.
        message: str - Text for a human.
        details: list[ErrorDetail] | None -
            Claims to individual fields, if the error is due to validation.
        request_id: str - Opaque request identifier for support.

    """

    error: str
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str
