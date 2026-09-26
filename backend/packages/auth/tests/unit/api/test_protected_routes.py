"""A protected request whole: markers, revocation, the kill switch, `/auth/me`."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, cast, override

import pytest
from auth_app import (
    FRONTEND_ORIGIN,
    Deps,
    bearer,
    build,
    client_for,
    seed,
)
from auth_fakes import NOW, FakeRevocationStore
from fastapi import APIRouter
from fastapi.routing import APIRoute, iter_route_contexts

# At run time: FastAPI resolves annotations through `__globals__`, and a `Request`
# under TYPE_CHECKING would become a query parameter.
from starlette.requests import Request  # ruff: ignore[typing-only-third-party-import]

from vld.auth.application import RevocationCheckUnavailableError
from vld.auth.domain import Role
from vld.web.access import AccessMarker, admin, current_identity, roles
from vld.web.errors import CoreErrorCode, ErrorRegistry
from vld.web.mounting import DomainDescriptor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient


class _ProductError(Exception):
    """Error base of a made-up domain: empty but required."""


_product_router = APIRouter(prefix="/product")


@_product_router.get("/feed", dependencies=[roles(Role.STUDENT)])
async def feed(request: Request) -> dict[str, object]:
    """Answer students only, with the role of the caller."""
    return {"role": current_identity(request).role}


@_product_router.get("/studio", dependencies=[admin()])
async def studio() -> dict[str, str]:
    """Answer admins only."""
    return {"ok": "yes"}


PRODUCT_DOMAIN = DomainDescriptor(
    router=_product_router,
    errors=ErrorRegistry(
        base=_ProductError,
        mapping={},
        fallback_code=CoreErrorCode.INTERNAL_ERROR,
    ),
    providers=(),
)


@pytest.fixture
async def app_and_deps() -> AsyncIterator[tuple[AsyncClient, Deps]]:
    """Give a client of auth plus the made-up product domain."""
    app, deps = build(None, PRODUCT_DOMAIN)
    async with client_for(app) as client:
        yield client, deps


def test_every_mounted_route_carries_exactly_one_access_marker() -> None:
    """No route lacks a marker, checked by walking the app, not by a list."""
    app, _ = build()
    routes = [
        context
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    ]

    unmarked = [
        f"{sorted(context.methods or set())} {context.path}"
        for context in routes
        if sum(
            isinstance(dependency, AccessMarker)
            for dependency in cast("APIRoute", context.original_route).dependencies
        )
        != 1
    ]

    assert unmarked == []
    paths = {context.path for context in routes}
    assert "/auth/login" in paths, "the walk found no routes; it is vacuous again"
    assert "/admin/users" in paths


async def test_a_teacher_is_refused_on_a_students_endpoint(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A role outside the marker is a 403."""
    client, deps = app_and_deps
    _ = await seed(deps, "t@b.co", role=Role.TEACHER)

    response = await client.get("/product/feed", headers=await bearer(client, "t@b.co"))

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "core.access_denied"


async def test_an_admin_passes_admin_but_not_a_roles_marker_it_is_not_in(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The admin flag opens `admin()` routes, not every role marker."""
    client, deps = app_and_deps
    _ = await seed(deps, "a@b.co", role=Role.TEACHER, is_admin=True)
    _ = await seed(deps, "s@b.co")
    admin_headers = await bearer(client, "a@b.co")
    student_headers = await bearer(client, "s@b.co")

    assert (await client.get("/product/feed", headers=admin_headers)).status_code == 403
    assert (
        await client.get("/product/studio", headers=admin_headers)
    ).status_code == 200
    assert (
        await client.get("/product/studio", headers=student_headers)
    ).status_code == 403
    assert (
        await client.get("/product/feed", headers=student_headers)
    ).status_code == 200


async def test_a_revoked_access_token_stops_working(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """After logout the access token is refused."""
    client, deps = app_and_deps
    _ = await seed(deps, "s@b.co")
    login = await client.post(
        "/auth/login",
        json={"email": "s@b.co", "password": "Correct Horse Battery"},
    )
    client.cookies.clear()
    pair = cast("dict[str, str]", login.json())
    headers = {"Authorization": f"Bearer {pair['access']}"}
    assert (await client.get("/product/feed", headers=headers)).status_code == 200

    logged_out = await client.post(
        "/auth/logout",
        json={"refresh": pair["refresh"]},
        headers=headers,
    )
    assert logged_out.status_code == HTTPStatus.NO_CONTENT

    after = await client.get("/product/feed", headers=headers)
    assert after.status_code == HTTPStatus.UNAUTHORIZED
    assert after.json()["error"] == "auth.token_revoked"


async def test_the_kill_switch_reaches_the_access_token(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Logging out everywhere cuts access tokens too."""
    client, deps = app_and_deps
    member = await seed(deps, "s@b.co")
    headers = await bearer(client, "s@b.co")

    member.invalidate_tokens(NOW)
    await deps.users.update(member)
    assert (await client.get("/product/feed", headers=headers)).status_code == 200

    member.invalidate_tokens(NOW + timedelta(seconds=1))
    await deps.users.update(member)
    cut = await client.get("/product/feed", headers=headers)

    assert cut.status_code == HTTPStatus.UNAUTHORIZED
    assert cut.json()["error"] == "auth.token_revoked"


async def test_a_deactivated_account_is_cut_off_at_once(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Deactivation works on the next request, not when the access token expires."""
    client, deps = app_and_deps
    member = await seed(deps, "s@b.co")
    headers = await bearer(client, "s@b.co")
    # Turned off without voiding the tokens, to see the state check itself.
    deps.users.items[member.id]._is_active = False

    response = await client.get("/product/feed", headers=headers)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "auth.account_deactivated"


async def test_a_deleted_account_is_told_apart(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A deleted account sends the client to the login screen."""
    client, deps = app_and_deps
    _ = await seed(deps, "s@b.co")
    headers = await bearer(client, "s@b.co")
    deps.users.items.clear()

    response = await client.get("/product/feed", headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"] == "auth.account_gone"


async def test_a_garbage_access_token_is_401_not_500(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A broken token maps to its code."""
    client, _ = app_and_deps

    response = await client.get("/product/feed", headers={"Authorization": "Bearer x"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"] == "auth.invalid_access_token"


async def test_a_refresh_token_is_not_accepted_as_an_access_token(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A long-lived token must not open what the short one opens."""
    client, deps = app_and_deps
    _ = await seed(deps, "s@b.co")
    login = await client.post(
        "/auth/login",
        json={"email": "s@b.co", "password": "Correct Horse Battery"},
    )
    client.cookies.clear()

    response = await client.get(
        "/product/feed",
        headers={"Authorization": f"Bearer {login.json()['refresh']}"},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"] == "auth.invalid_access_token"


async def test_an_unavailable_revocation_store_is_503_not_401() -> None:
    """A Redis flap is a 503 on protected routes, not a mass logout."""

    class _Unavailable(FakeRevocationStore):
        @override
        async def is_revoked(self, jti: str) -> bool:
            del jti
            msg = "revocation store is unavailable"
            raise RevocationCheckUnavailableError(msg)

    app, deps = build(Deps(revocation=_Unavailable()), PRODUCT_DOMAIN)
    async with client_for(app) as client:
        _ = await seed(deps, "s@b.co")
        response = await client.get(
            "/product/feed",
            headers=await bearer(client, "s@b.co"),
        )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.headers["Retry-After"]
    assert response.json()["error"] == "auth.revocation_check_unavailable"


async def test_logging_out_everywhere_also_empties_the_browser(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The session that asked is thrown out too."""
    client, deps = app_and_deps
    _ = await seed(deps, "s@b.co")
    headers = await bearer(client, "s@b.co")

    response = await client.post(
        "/auth/logout-all",
        headers={**headers, "Origin": FRONTEND_ORIGIN},
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    cleared = {
        raw.split("=", 1)[0]: raw for raw in response.headers.get_list("set-cookie")
    }
    assert set(cleared) == {"validate_access", "validate_refresh"}
    assert all("Max-Age=0" in raw for raw in cleared.values())


async def test_me_returns_the_account_behind_the_token(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The header and routing of the site read it; no token in the body."""
    client, deps = app_and_deps
    member = await seed(deps, "t@b.co", role=Role.TEACHER)

    response = await client.get("/auth/me", headers=await bearer(client, "t@b.co"))

    assert response.status_code == HTTPStatus.OK
    assert response.headers["cache-control"] == "no-store"
    body = cast("dict[str, object]", response.json())
    assert body == {
        "user_id": str(member.id),
        "email": "t@b.co",
        "email_verified": True,
        "role": "teacher",
        "is_admin": False,
        "profile": {
            "first_name_ru": None,
            "last_name_ru": None,
            "first_name_en": None,
            "last_name_en": None,
            "group_number": None,
            "institution_name": None,
        },
    }


async def test_me_requires_a_session(app_and_deps: tuple[AsyncClient, Deps]) -> None:
    """An anonymous caller gets a 401, not a body."""
    client, _ = app_and_deps

    response = await client.get("/auth/me")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
