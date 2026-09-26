"""Administration over HTTP: the admin marker and what admins may do."""

from __future__ import annotations

import uuid
from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, cast

import pytest
from auth_app import Deps, bearer, build, client_for, seed
from fastapi.routing import iter_route_contexts

from vld.auth.domain import AuthAuditAction, Role

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient


@pytest.fixture
async def app_and_deps() -> AsyncIterator[tuple[AsyncClient, Deps]]:
    """Give a client and the fakes behind it."""
    app, deps = build()
    async with client_for(app) as client:
        yield client, deps


async def _admin(client: AsyncClient, deps: Deps) -> dict[str, str]:
    _ = await seed(deps, "admin@b.co", role=Role.TEACHER, is_admin=True)
    return await bearer(client, "admin@b.co")


def test_the_admin_routes_are_mounted() -> None:
    """Without this the marker walk would be green on an app without the panel."""
    app, _ = build()

    paths = {context.path for context in iter_route_contexts(app.routes)}

    assert {
        "/admin/users",
        "/admin/users/{user_id}",
        "/admin/users/{user_id}/active",
        "/admin/users/{user_id}/role",
        "/admin/audit",
    } <= paths


@pytest.mark.parametrize("role", [Role.STUDENT, Role.TEACHER])
async def test_a_non_admin_is_refused(
    app_and_deps: tuple[AsyncClient, Deps],
    role: Role,
) -> None:
    """No role opens the panel without the admin flag."""
    client, deps = app_and_deps
    _ = await seed(deps, "u@b.co", role=role)
    headers = await bearer(client, "u@b.co")

    for path in ("/admin/users", "/admin/audit"):
        response = await client.get(path, headers=headers)
        assert response.status_code == HTTPStatus.FORBIDDEN, path


async def test_an_admin_reads_the_list_with_filters(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The list is paged, filtered and counts the matches."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)
    _ = await seed(deps, "s1@b.co")
    _ = await seed(deps, "s2@b.co", is_active=False)
    _ = await seed(deps, "t@b.co", role=Role.TEACHER)

    response = await client.get(
        "/admin/users",
        params={"role": "student", "is_active": "true"},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.OK
    page = cast("dict[str, object]", response.json())
    items = cast("list[dict[str, object]]", page["items"])
    assert page["total"] == 1
    assert [item["email"] for item in items] == ["s1@b.co"]
    assert set(items[0]) == {
        "id",
        "email",
        "email_verified",
        "role",
        "is_admin",
        "is_active",
        "profile",
    }


async def test_the_list_refuses_a_bottomless_offset(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """A deep offset is refused by the schema, not by a table scan."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)

    response = await client.get("/admin/users?offset=5000000", headers=headers)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_the_card_answers_404_for_an_unknown_id(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """An unknown id is a normal 404."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)

    response = await client.get(f"/admin/users/{uuid.uuid4()}", headers=headers)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"] == "auth.user_not_found"


async def test_deactivation_cuts_the_account_off_and_is_audited(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Deactivation cuts the account off at once and ends its sessions for good."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)
    member = await seed(deps, "s@b.co")
    member_headers = await bearer(client, "s@b.co")
    deps.clock.advance(timedelta(seconds=5))

    off = await client.put(
        f"/admin/users/{member.id}/active",
        json={"is_active": False},
        headers=headers,
    )
    cut = await client.get("/auth/me", headers=member_headers)
    on = await client.put(
        f"/admin/users/{member.id}/active",
        json={"is_active": True},
        headers=headers,
    )

    assert off.status_code == HTTPStatus.OK
    assert off.json()["is_active"] is False
    assert cut.status_code == HTTPStatus.FORBIDDEN
    assert cut.json()["error"] == "auth.account_deactivated"
    assert on.json()["is_active"] is True
    # Activation gives access back, not the sessions deactivation ended.
    stale = await client.get("/auth/me", headers=member_headers)
    assert stale.status_code == HTTPStatus.UNAUTHORIZED
    assert stale.json()["error"] == "auth.token_revoked"
    actions = [
        entry.action for entry in deps.audit.entries if entry.target_id == member.id
    ]
    assert actions == [AuthAuditAction.USER_DEACTIVATED, AuthAuditAction.USER_ACTIVATED]


async def test_an_admin_cannot_turn_off_another_admin_or_self(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """Admins are managed from the console only."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)
    me = await deps.users.get_by_email("admin@b.co")
    other = await seed(deps, "other@b.co", is_admin=True)
    assert me is not None

    for target in (me, other):
        response = await client.put(
            f"/admin/users/{target.id}/active",
            json={"is_active": False},
            headers=headers,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json()["error"] == "auth.target_forbidden"


async def test_an_admin_changes_a_role_and_it_lands_in_the_audit(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The record keeps both roles."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)
    member = await seed(deps, "s@b.co")

    response = await client.put(
        f"/admin/users/{member.id}/role",
        json={"role": "teacher"},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["role"] == "teacher"
    [entry] = [
        e for e in deps.audit.entries if e.action is AuthAuditAction.USER_ROLE_CHANGED
    ]
    assert entry.payload == {"from": "student", "to": "teacher"}


async def test_an_admin_reads_the_audit_with_filters(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The audit is read by page; the target filter really applies."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)
    member = await seed(deps, "s@b.co")
    _ = await client.put(
        f"/admin/users/{member.id}/role",
        json={"role": "teacher"},
        headers=headers,
    )

    everything = await client.get("/admin/audit", headers=headers)
    by_target = await client.get(
        "/admin/audit",
        params={"target_id": str(member.id)},
        headers=headers,
    )
    by_nobody = await client.get(
        "/admin/audit",
        params={"actor_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert everything.status_code == HTTPStatus.OK
    actions = [item["action"] for item in everything.json()["items"]]
    assert {"login_succeeded", "user_role_changed"} <= set(actions)
    assert by_target.json()["total"] == 1
    assert by_target.json()["items"][0]["action"] == "user_role_changed"
    assert by_nobody.json()["total"] == 0


async def test_audit_page_carries_the_total_and_echoes_its_bounds(
    app_and_deps: tuple[AsyncClient, Deps],
) -> None:
    """The page is numbered and shifts by its offset."""
    client, deps = app_and_deps
    headers = await _admin(client, deps)
    _ = await seed(deps, "s@b.co")
    _ = await bearer(client, "s@b.co")

    first = cast(
        "dict[str, object]",
        (await client.get("/admin/audit?limit=5", headers=headers)).json(),
    )
    shifted = cast(
        "dict[str, object]",
        (await client.get("/admin/audit?limit=5&offset=1", headers=headers)).json(),
    )

    assert set(first) == {"items", "total", "limit", "offset"}
    assert (first["limit"], first["offset"]) == (5, 0)
    assert (shifted["limit"], shifted["offset"]) == (5, 1)
    head = cast("list[object]", first["items"])
    assert len(head) >= 2, "two logins must have left two records"
    assert shifted["items"] == head[1:]
