"""Mounting domain descriptors into the FastAPI application."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi.routing import APIRoute, iter_route_contexts

from vld.web.access import (
    ACCESS_ERRORS,
    PROTECTED_ERROR_RESPONSES,
    AccessMarker,
    UnmarkedRouteError,
    require_same_origin,
)
from vld.web.errors import COMMON_ERROR_RESPONSES, CORE_ERRORS, register_error_handlers

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.routing import BaseRoute

    from ._descriptor import DomainDescriptor


def mount(app: FastAPI, *domains: DomainDescriptor, prefix: str = "") -> None:
    """Mount the domains: their routers and error registries.

    Every route must carry exactly one access marker, otherwise mounting fails with
    `UnmarkedRouteError`: a route without a check cannot reach the application.

    Args:
        app: FastAPI - Application.
        domains: DomainDescriptor - Descriptors of the mounted domains.
        prefix: str - Common prefix, for example ``/api/v1``.

    """
    register_error_handlers(
        app,
        *(domain.errors for domain in domains),
        CORE_ERRORS,
        ACCESS_ERRORS,
    )
    for domain in domains:
        for context in iter_route_contexts(domain.router.routes):
            _require_marker(context.original_route)
        app.include_router(
            domain.router,
            prefix=prefix,
            responses=COMMON_ERROR_RESPONSES,
            dependencies=[Depends(require_same_origin)],
        )


def _require_marker(route: BaseRoute) -> None:
    """Require an explicit access marker from the route and declare its statuses.

    Args:
        route: BaseRoute - Mounted router route.

    Raises:
        UnmarkedRouteError: if there is no marker or there are more than one.

    """
    if not isinstance(route, APIRoute):
        return
    markers = [dep for dep in route.dependencies if isinstance(dep, AccessMarker)]
    if len(markers) != 1:
        msg = (
            f"route {sorted(route.methods or set())} {route.path} carries "
            f"{len(markers)} access markers instead of one: every route must "
            f"declare public(), authenticated(), roles(...), staff(...) or admin()"
        )
        raise UnmarkedRouteError(msg)
    if not markers[0].anonymous:
        route.responses = {**PROTECTED_ERROR_RESPONSES, **route.responses}
