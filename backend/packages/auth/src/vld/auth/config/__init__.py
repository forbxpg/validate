"""Settings of the auth domain, with the variable names of doi-arxiv-app."""

from __future__ import annotations

from ._jwt import MIN_JWT_SECRET_BYTES, JwtSettings

__all__ = ("MIN_JWT_SECRET_BYTES", "JwtSettings")
