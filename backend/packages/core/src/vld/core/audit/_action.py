"""List of auditable actions."""

from __future__ import annotations

from enum import StrEnum


class AuditAction(StrEnum):
    """What event happened.

    Attributes:
        LOGIN_SUCCEEDED: A user logged in.
        LOGIN_FAILED: A login attempt was refused.
        LOGGED_OUT: A user ended a session.
        SESSIONS_INVALIDATED: Every session of a user was ended at once.
        PASSWORD_CHANGED: A user changed their password while logged in.
        PASSWORD_RESET: A password was set through a link from a letter.
        USER_DEACTIVATED: An admin turned an account off.
        USER_ACTIVATED: An admin turned an account back on.
        USER_ROLE_CHANGED: An admin changed the role of an account.
        ADMIN_GRANTED: The admin flag was set from the console.
        USER_DELETED: An account was deleted from the console.

    """

    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    LOGGED_OUT = "logged_out"
    SESSIONS_INVALIDATED = "sessions_invalidated"
    PASSWORD_CHANGED = "password_changed"  # ruff: ignore[hardcoded-password-string]
    PASSWORD_RESET = "password_reset"  # ruff: ignore[hardcoded-password-string]
    USER_DEACTIVATED = "user_deactivated"
    USER_ACTIVATED = "user_activated"
    USER_ROLE_CHANGED = "user_role_changed"
    ADMIN_GRANTED = "admin_granted"
    USER_DELETED = "user_deleted"
