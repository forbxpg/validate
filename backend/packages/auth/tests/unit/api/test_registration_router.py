"""Registration over HTTP: the roles one may pick, the profile, length caps."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from auth_app import CREDENTIALS, REGISTRATION, build, client_for
from auth_fakes import GOOD_PASSWORD

from vld.auth.api.schemas._limits import (
    MAX_EMAIL_TOKEN,
    MAX_JWT,
    MAX_NAME,
    MAX_PASSWORD,
)
from vld.auth.domain import Profile, Role

_OVERSIZED = 10_000


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_can_be_picked_at_registration(role: Role) -> None:
    """Students and teachers pick their role themselves."""
    app, deps = build()
    async with client_for(app) as client:
        response = await client.post(
            "/auth/register",
            json={"email": "r@b.co", "password": GOOD_PASSWORD, "role": role.value},
        )

    assert response.status_code == HTTPStatus.CREATED
    [user] = deps.users.items.values()
    assert user.role is role


async def test_admin_rights_cannot_be_claimed_at_registration() -> None:
    """There is no admin role, and an `is_admin` field is ignored."""
    app, deps = build()
    async with client_for(app) as client:
        as_role = await client.post(
            "/auth/register",
            json={"email": "a@b.co", "password": GOOD_PASSWORD, "role": "admin"},
        )
        as_flag = await client.post(
            "/auth/register",
            json={**REGISTRATION, "is_admin": True},
        )

    assert as_role.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert as_flag.status_code == HTTPStatus.CREATED
    assert not any(user.is_admin for user in deps.users.items.values())


async def test_the_profile_given_at_registration_is_stored() -> None:
    """The details of the form reach the account."""
    app, deps = build()
    async with client_for(app) as client:
        response = await client.post(
            "/auth/register",
            json={
                **REGISTRATION,
                "profile": {"last_name_ru": "Иванов", "institution_name": "НИЯУ МИФИ"},
            },
        )

    assert response.status_code == HTTPStatus.CREATED
    [user] = deps.users.items.values()
    assert user.profile == Profile(last_name_ru="Иванов", institution_name="НИЯУ МИФИ")


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/auth/register", {**REGISTRATION, "password": "x" * _OVERSIZED}),
        ("/auth/login", {**CREDENTIALS, "password": "x" * _OVERSIZED}),
    ],
)
async def test_oversized_password_is_rejected_before_hashing(
    path: str,
    payload: dict[str, str],
) -> None:
    """A password over the cap is refused by validation, never hashed."""
    app, deps = build()
    async with client_for(app) as client:
        response = await client.post(path, json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert deps.hasher.hashed == [], "hashing must not be reached"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/auth/refresh", {"refresh": "x" * (MAX_JWT + 1)}),
        ("/auth/verify-email", {"token": "x" * (MAX_EMAIL_TOKEN + 1)}),
        (
            "/auth/register",
            {**REGISTRATION, "profile": {"first_name_ru": "x" * (MAX_NAME + 1)}},
        ),
    ],
    ids=["refresh", "verification-token", "profile-name"],
)
async def test_oversized_strings_are_rejected(
    path: str,
    payload: dict[str, object],
) -> None:
    """Every string that arrives has a cap."""
    app, _ = build()
    async with client_for(app) as client:
        response = await client.post(path, json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_the_byte_limit_of_bcrypt_is_a_domain_refusal() -> None:
    """Within the character cap but over 72 bytes, the policy refuses it."""
    app, deps = build()
    password = "Aa" + "ю" * 36
    assert len(password) <= MAX_PASSWORD
    async with client_for(app) as client:
        response = await client.post(
            "/auth/register",
            json={**REGISTRATION, "password": password},
        )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"] == "auth.weak_password"
    assert deps.users.items == {}
