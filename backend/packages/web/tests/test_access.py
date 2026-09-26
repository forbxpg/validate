"""Access mechanics without a domain: markers, deny by default, roles."""

from __future__ import annotations

import uuid
from typing import cast

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from fastapi import APIRouter, FastAPI, Request
from httpx import ASGITransport, AsyncClient

from vld.web.access import (
    ACCESS_COOKIE,
    AccessMarker,
    Identity,
    IdentityProvider,
    UnmarkedRouteError,
    admin,
    authenticated,
    current_identity,
    public,
    roles,
    self_authenticated,
    staff,
)
from vld.web.errors import CoreErrorCode, ErrorRegistry
from vld.web.mounting import DomainDescriptor, mount

STUDENT = "student"
TEACHER = "teacher"
GUEST = "guest"

USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


class _StubError(Exception):
    pass


_ERRORS = ErrorRegistry(
    base=_StubError,
    mapping={},
    fallback_code=CoreErrorCode.INTERNAL_ERROR,
)


class _StubProvider:
    def __init__(self, identity: Identity | None = None) -> None:
        self.identity: Identity | None = identity
        self.calls: list[str] = []

    async def identify(self, token: str) -> Identity:
        self.calls.append(token)
        if self.identity is None:
            msg = "token is not good"
            raise _StubError(msg)
        return self.identity


async def _thing(request: Request) -> dict[str, object]:
    identity = current_identity(request)
    return {"role": identity.role, "is_admin": identity.is_admin}


async def _ok() -> dict[str, str]:
    return {"ok": "yes"}


def _build(
    marker: AccessMarker | None,
    provider: _StubProvider,
    *,
    extra_marker: AccessMarker | None = None,
) -> FastAPI:
    router = APIRouter()
    dependencies = [dep for dep in (marker, extra_marker) if dep is not None]
    _ = router.get("/thing", dependencies=dependencies)(_thing)
    _ = router.get("/anonymous", dependencies=[public()])(_ok)
    _ = router.get("/own", dependencies=[self_authenticated()])(_ok)

    class _Adapters(Provider):
        @provide(scope=Scope.APP)
        def identity_provider(self) -> IdentityProvider:
            return provider

    app = FastAPI()
    mount(app, DomainDescriptor(router=router, errors=_ERRORS, providers=()))
    setup_dishka(make_async_container(_Adapters()), app)
    return app


def _responses(schema: dict[str, object], path: str) -> dict[str, object]:
    paths = cast("dict[str, dict[str, dict[str, dict[str, object]]]]", schema["paths"])
    return paths[path]["get"]["responses"]


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _get_thing(app: FastAPI) -> tuple[int, object]:
    async with _client(app) as client:
        response = await client.get("/thing", headers={"Authorization": "Bearer t"})
    return response.status_code, response.json()


@pytest.fixture
def teacher_admin() -> Identity:
    """Give a teacher who also has the admin flag."""
    return Identity(user_id=USER_ID, role=TEACHER, is_admin=True)


def test_an_unmarked_route_refuses_to_mount() -> None:
    """Deny by default: a forgotten check cannot reach the application."""
    router = APIRouter()
    _ = router.get("/forgotten")(_ok)

    with pytest.raises(UnmarkedRouteError, match="forgotten"):
        mount(FastAPI(), DomainDescriptor(router=router, errors=_ERRORS, providers=()))


def test_a_nested_unmarked_route_refuses_to_mount() -> None:
    """The check walks nested routers, not only the top one."""
    inner = APIRouter()
    _ = inner.get("/deep")(_ok)
    middle = APIRouter()
    middle.include_router(inner)
    outer = APIRouter()
    outer.include_router(middle)

    with pytest.raises(UnmarkedRouteError, match="deep"):
        mount(FastAPI(), DomainDescriptor(router=outer, errors=_ERRORS, providers=()))


def test_two_markers_on_one_route_refuse_to_mount() -> None:
    """Two role lists on one route would make the result depend on their order."""
    with pytest.raises(UnmarkedRouteError, match="2 access markers"):
        _ = _build(roles(STUDENT), _StubProvider(), extra_marker=roles(TEACHER))


@pytest.mark.parametrize("marker", [roles, staff])
def test_a_role_list_without_roles_is_refused(marker: object) -> None:
    """An empty list reads as "any role" but would mean "nobody"."""
    assert callable(marker)
    with pytest.raises(ValueError, match="at least one role"):
        _ = marker()


async def test_a_public_route_does_not_ask_for_identity() -> None:
    """Registration has no token, so a public route must not look for one."""
    provider = _StubProvider()
    async with _client(_build(public(), provider)) as client:
        response = await client.get("/anonymous")

    assert response.status_code == 200
    assert provider.calls == []


@pytest.mark.parametrize(
    "header",
    [None, "", "Basic zzz", "Bearer", "Bearer   "],
    ids=["missing", "empty", "wrong-scheme", "no-token", "blank-token"],
)
async def test_a_protected_route_without_a_token_is_401(
    header: str | None,
    teacher_admin: Identity,
) -> None:
    """Every shape of "no token" is a 401, never a 500 or a 200."""
    provider = _StubProvider(teacher_admin)
    headers = {} if header is None else {"Authorization": header}
    async with _client(_build(authenticated(), provider)) as client:
        response = await client.get("/thing", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"] == "core.not_authenticated"
    assert provider.calls == []


async def test_authenticated_admits_any_role() -> None:
    """`authenticated()` only needs a valid token."""
    guest = Identity(user_id=USER_ID, role=GUEST, is_admin=False)

    status, _ = await _get_thing(_build(authenticated(), _StubProvider(guest)))

    assert status == 200


async def test_a_role_outside_the_list_is_403() -> None:
    """Roles are admitted by listing them, never by excluding the others."""
    guest = Identity(user_id=USER_ID, role=GUEST, is_admin=False)

    status, body = await _get_thing(
        _build(roles(STUDENT, TEACHER), _StubProvider(guest)),
    )

    assert status == 403
    assert cast("dict[str, object]", body)["error"] == "core.access_denied"


async def test_roles_do_not_let_the_admin_flag_in(teacher_admin: Identity) -> None:
    """The admin flag is a separate dimension, not a key to other roles."""
    status, _ = await _get_thing(_build(roles(STUDENT), _StubProvider(teacher_admin)))

    assert status == 403


async def test_staff_admits_a_listed_role_without_the_admin_flag() -> None:
    """A teacher reaches a staff route by role alone."""
    teacher = Identity(user_id=USER_ID, role=TEACHER, is_admin=False)

    status, body = await _get_thing(_build(staff(TEACHER), _StubProvider(teacher)))

    assert status == 200
    assert body == {"role": TEACHER, "is_admin": False}


async def test_staff_admits_the_admin_flag_whatever_the_role() -> None:
    """An admin reaches a staff route even with an unlisted role."""
    student_admin = Identity(user_id=USER_ID, role=STUDENT, is_admin=True)

    status, _ = await _get_thing(_build(staff(TEACHER), _StubProvider(student_admin)))

    assert status == 200


async def test_staff_refuses_a_user_without_the_role_or_the_flag() -> None:
    """`staff()` is not `authenticated()`: a valid token is not enough."""
    student = Identity(user_id=USER_ID, role=STUDENT, is_admin=False)

    status, _ = await _get_thing(_build(staff(TEACHER), _StubProvider(student)))

    assert status == 403


async def test_admin_admits_the_flag_whatever_the_role(teacher_admin: Identity) -> None:
    """`admin()` looks at the flag only."""
    status, body = await _get_thing(_build(admin(), _StubProvider(teacher_admin)))

    assert status == 200
    assert body == {"role": TEACHER, "is_admin": True}


async def test_admin_refuses_every_role_without_the_flag() -> None:
    """`admin()` lists no roles, so no role gets in on its own."""
    teacher = Identity(user_id=USER_ID, role=TEACHER, is_admin=False)

    status, _ = await _get_thing(_build(admin(), _StubProvider(teacher)))

    assert status == 403


async def test_a_domain_refusal_is_not_swallowed_into_a_200() -> None:
    """When the domain refuses the token, the route does not run."""
    provider = _StubProvider()

    status, _ = await _get_thing(_build(authenticated(), provider))

    assert status == 500
    assert provider.calls == ["t"]


def test_protected_routes_declare_401_and_403_but_public_ones_do_not(
    teacher_admin: Identity,
) -> None:
    """A client generated from the schema rejects an undeclared status."""
    schema = _build(roles(TEACHER), _StubProvider(teacher_admin)).openapi()

    assert {"401", "403"} <= _responses(schema, "/thing").keys()
    assert not {"401", "403"} & _responses(schema, "/anonymous").keys()


async def test_a_self_authenticated_route_is_admitted_without_a_token() -> None:
    """A route with its own credential checks it itself."""
    provider = _StubProvider()
    async with _client(_build(public(), provider)) as client:
        response = await client.get("/own")

    assert response.status_code == 200
    assert provider.calls == []


def test_self_authenticated_differs_from_public_in_the_marker() -> None:
    """A route with no check and a route with its own check are told apart."""
    own = self_authenticated()

    assert own.anonymous
    assert own.self_authenticating
    assert not public().self_authenticating


async def test_a_marker_reads_the_token_from_the_cookie(
    teacher_admin: Identity,
) -> None:
    """A browser sends the token as a cookie, not as a header."""
    provider = _StubProvider(teacher_admin)
    async with _client(_build(authenticated(), provider)) as client:
        response = await client.get(
            "/thing",
            headers={"Cookie": f"{ACCESS_COOKIE}=cookie-token"},
        )

    assert response.status_code == 200
    assert provider.calls == ["cookie-token"]
