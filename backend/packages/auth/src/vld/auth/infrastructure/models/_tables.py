"""Names of the auth schema, its tables and types."""

from __future__ import annotations

SCHEMA = "auth"

USERS = "users"
VERIFICATION_TOKENS = "verification_tokens"
OUTBOX = "outbox"

ROLE = "role"
TOKEN_PURPOSE = "token_purpose"  # ruff: ignore[hardcoded-password-string] -- a type name
OUTBOX_STATUS = "outbox_status"

QUALIFIED_USERS = f"{SCHEMA}.{USERS}"
QUALIFIED_VERIFICATION_TOKENS = f"{SCHEMA}.{VERIFICATION_TOKENS}"
QUALIFIED_OUTBOX = f"{SCHEMA}.{OUTBOX}"

EMAIL_UNIQUE_CONSTRAINT = f"uq_{USERS}_email"
EMAIL_LOWER_CASE_CONSTRAINT = "email_lower_case"
