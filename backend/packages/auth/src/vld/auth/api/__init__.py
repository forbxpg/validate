"""HTTP layer of auth: the descriptor and the public contract of errors."""

from __future__ import annotations

from ._domain import AUTH_DOMAIN
from .schemas import AuthErrorCode, AuthErrorResponse

__all__ = (
    "AUTH_DOMAIN",
    "AuthErrorCode",
    "AuthErrorResponse",
)
