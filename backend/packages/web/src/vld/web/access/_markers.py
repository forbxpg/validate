"""Marker of routes: marker is a check."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import params
from starlette.requests import Request

from ._cookie import access_token
from ._errors import AccessDeniedError, NotAuthenticatedError
from ._identity import Identity, IdentityProvider

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from dishka import AsyncContainer


class AccessMarker(params.Depends):
    """Dependency-marker of the route.

    Attributes:
        allowed: frozenset[str] | None - Allowed roles.
        anonymous: bool - Allows the marker without the access token.
        self_authenticating: bool - Checks the route itself by its own credential.

    """

    allowed: frozenset[str] | None
    anonymous: bool
    self_authenticating: bool

    def __init__(
        self,
        allowed: frozenset[str] | None,
        *,
        anonymous: bool,
        self_authenticating: bool = False,
        admin_bypass: bool = False,
    ) -> None:
        super().__init__(
            dependency=_check(
                allowed,
                anonymous=anonymous,
                admin_bypass=admin_bypass,
            ),
        )
        self.allowed = allowed
        self.anonymous = anonymous
        self.self_authenticating = self_authenticating


def public() -> AccessMarker:
    """Allow anyone: registration, login, address confirmation.

    Returns:
        AccessMarker - Marker, not checking anything.

    """
    return AccessMarker(None, anonymous=True)


def self_authenticated() -> AccessMarker:
    """The route is authenticated by its own credential, not by the access token.

    Returns:
        AccessMarker - Marker of the route with its own authentication.

    """
    return AccessMarker(None, anonymous=True, self_authenticating=True)


def authenticated() -> AccessMarker:
    """An access token is needed and any role is allowed.

    Returns:
        AccessMarker - Marker without restriction by role.

    """
    return AccessMarker(None, anonymous=False)


def roles(*allowed: str) -> AccessMarker:
    """An access token is needed and a role from the listed ones.

    Args:
        allowed: str - Allowed roles.

    Returns:
        AccessMarker - Marker with the list of allowed roles.

    Raises:
        ValueError: if no roles are listed.

    """
    if not allowed:
        msg = "roles() requires at least one role; use authenticated() instead"
        raise ValueError(msg)
    return AccessMarker(frozenset(allowed), anonymous=False)


def staff(*allowed: str) -> AccessMarker:
    """An access token is needed and a role from the listed ones or the admin flag.

    Args:
        allowed: str - Roles allowed along with the admin.

    Returns:
        AccessMarker - Marker with the list of roles and the admin flag bypass.

    Raises:
        ValueError: if no roles are listed.

    """
    if not allowed:
        msg = "staff() requires at least one role; use admin() for admin-only"
        raise ValueError(msg)
    return AccessMarker(frozenset(allowed), anonymous=False, admin_bypass=True)


def admin() -> AccessMarker:
    """An access token is needed and the admin flag; no role is allowed.

    Returns:
        AccessMarker - Marker with an empty list of roles and the admin flag bypass.

    """
    return AccessMarker(frozenset(), anonymous=False, admin_bypass=True)


def current_identity(request: Request) -> Identity:
    """Identity established by the marker of this route.

    Args:
        request: Request - Request.

    Returns:
        Identity - Owner of the presented token.

    Raises:
        NotAuthenticatedError: if the route is marked with `public()`.

    """
    identity = getattr(request.state, "identity", None)
    if not isinstance(identity, Identity):
        msg = "route is public: no identity was established"
        raise NotAuthenticatedError(msg)
    return identity


def _check(
    allowed: frozenset[str] | None,
    *,
    anonymous: bool,
    admin_bypass: bool = False,
) -> Callable[[Request], Coroutine[object, object, None]]:
    """Collect the checking function of the marker.

    Args:
        allowed: frozenset[str] | None - Allowed roles, ``None`` — any.
        anonymous: bool - Allow without the token.
        admin_bypass: bool - Allow with the admin flag independently of the role.

    Returns:
        Callable[[Request], Coroutine[object, object, None]] - Dependency of FastAPI,
            rejecting the request by exception.

    """

    async def _run_identity_check(request: Request) -> None:
        if anonymous:
            return

        container = cast("AsyncContainer", request.state.dishka_container)
        provider = await container.get(IdentityProvider)
        identity = await provider.identify(access_token(request))
        admitted = (
            allowed is None
            or identity.role in allowed
            or (admin_bypass and identity.is_admin)
        )
        if not admitted:
            msg = f"role {identity.role} is not allowed here"
            raise AccessDeniedError(msg)

        request.state.identity = identity

    return _run_identity_check
