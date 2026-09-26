"""ORM models of the auth schema, one module per entity."""

from __future__ import annotations

from ._base import METADATA, AuthBase
from ._tables import (
    EMAIL_LOWER_CASE_CONSTRAINT,
    EMAIL_UNIQUE_CONSTRAINT,
    OUTBOX,
    OUTBOX_STATUS,
    QUALIFIED_OUTBOX,
    QUALIFIED_USERS,
    QUALIFIED_VERIFICATION_TOKENS,
    ROLE,
    SCHEMA,
    TOKEN_PURPOSE,
    USERS,
    VERIFICATION_TOKENS,
)

__all__ = (
    "EMAIL_LOWER_CASE_CONSTRAINT",
    "EMAIL_UNIQUE_CONSTRAINT",
    "METADATA",
    "OUTBOX",
    "OUTBOX_STATUS",
    "QUALIFIED_OUTBOX",
    "QUALIFIED_USERS",
    "QUALIFIED_VERIFICATION_TOKENS",
    "ROLE",
    "SCHEMA",
    "TOKEN_PURPOSE",
    "USERS",
    "VERIFICATION_TOKENS",
    "AuthBase",
)
