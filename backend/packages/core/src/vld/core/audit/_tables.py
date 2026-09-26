"""Names of the audit schema and table."""

from __future__ import annotations

AUDIT_SCHEMA_NAME = "audit"
AUDIT_LOG_TABLE_NAME = "log"

QUALIFIED_AUDIT_LOG_TABLE_NAME = f"{AUDIT_SCHEMA_NAME}.{AUDIT_LOG_TABLE_NAME}"

APPEND_ONLY_FUNCTION = f"{AUDIT_SCHEMA_NAME}.reject_audit_mutation"
APPEND_ONLY_TRIGGER = "trg_log_append_only"
APPEND_ONLY_TRUNCATE_TRIGGER = "trg_log_no_truncate"
"""Qualified names of the audit log table and its functions and triggers."""
