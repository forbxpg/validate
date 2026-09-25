"""List of auditable actions."""

from __future__ import annotations

from enum import StrEnum


class AuditAction(StrEnum):
    """What event happened.

    Attributes:
        LOGIN_SUCCEEDED: User logged in successfully.
        LOGIN_FAILED: User failed to log in.
        LOGGED_OUT: User logged out.
        SESSIONS_INVALIDATED: User's sessions were invalidated.
        USER_REGISTERED: User registered.
        USER_BANNED: User was banned.
        USER_UNBANNED: User was unbanned.
        USER_ROLE_CHANGED: User's role was changed.
        STAFF_CREATED: Staff user was created.
        IDENTITY_LINKED: Identity was linked to a user.
        IDENTITY_UNLINKED: Identity was unlinked from a user.

    """

    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    LOGGED_OUT = "logged_out"
    SESSIONS_INVALIDATED = "sessions_invalidated"
    USER_REGISTERED = "user_registered"
    USER_BANNED = "user_banned"
    USER_UNBANNED = "user_unbanned"
    USER_ROLE_CHANGED = "user_role_changed"
    STAFF_CREATED = "staff_created"
    IDENTITY_LINKED = "identity_linked"
    IDENTITY_UNLINKED = "identity_unlinked"
