"""Enumerations of the auth domain."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Role a user picks at registration; admin rights are a separate flag."""

    STUDENT = "student"
    TEACHER = "teacher"


class TokenPurpose(StrEnum):
    """What a one-time token from a letter is for."""

    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"  # ruff: ignore[hardcoded-password-string]
