"""Settings of the auth domain, with the variable names of doi-arxiv-app."""

from __future__ import annotations

from ._jwt import MIN_JWT_SECRET_BYTES, JwtSettings
from ._password import PasswordSettings
from ._verification import VerificationSettings

__all__ = (
    "MIN_JWT_SECRET_BYTES",
    "JwtSettings",
    "PasswordSettings",
    "VerificationSettings",
)
