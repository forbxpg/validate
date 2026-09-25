"""Who may call a route: markers, session cookies, identity, Origin check."""

from __future__ import annotations

from ._bearer_token import bearer
from ._cookie import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    access_token,
    clear_session_cookies,
    presented_access_token,
    set_session_cookies,
)
from ._errors import (
    ACCESS_ERRORS,
    PROTECTED_ERROR_RESPONSES,
    AccessDeniedError,
    NotAuthenticatedError,
    UnmarkedRouteError,
)
from ._identity import Identity, IdentityProvider
from ._markers import (
    AccessMarker,
    admin,
    authenticated,
    current_identity,
    public,
    roles,
    self_authenticated,
    staff,
)
from ._optional import optional_identity
from ._origin import require_same_origin

__all__ = (
    "ACCESS_COOKIE",
    "ACCESS_ERRORS",
    "PROTECTED_ERROR_RESPONSES",
    "REFRESH_COOKIE",
    "AccessDeniedError",
    "AccessMarker",
    "Identity",
    "IdentityProvider",
    "NotAuthenticatedError",
    "UnmarkedRouteError",
    "access_token",
    "admin",
    "authenticated",
    "bearer",
    "clear_session_cookies",
    "current_identity",
    "optional_identity",
    "presented_access_token",
    "public",
    "require_same_origin",
    "roles",
    "self_authenticated",
    "set_session_cookies",
    "staff",
)
