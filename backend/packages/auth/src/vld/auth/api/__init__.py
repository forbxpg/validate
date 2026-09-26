"""HTTP layer of auth: the descriptor and the public contract of errors."""

from __future__ import annotations

from .schemas import AuthErrorCode, AuthErrorResponse

__all__ = ("AuthErrorCode", "AuthErrorResponse")
