"""The `AuthApi` contract: whom auth treats as acting in the system."""

from __future__ import annotations

import uuid

from auth_fakes import NOW, FakeUserRepository

from vld.auth.domain import Role, User
from vld.auth.infrastructure import AuthApiAdapter


async def _stored(*, active: bool) -> tuple[AuthApiAdapter, uuid.UUID]:
    users = FakeUserRepository()
    user = User(
        id=uuid.uuid4(),
        email="someone@example.com",
        email_verified_at=NOW,
        password_hash="hashed:pw",
        role=Role.TEACHER,
        is_admin=False,
        is_active=active,
    )
    await users.add(user)
    return AuthApiAdapter(users), user.id


async def test_an_active_account_answers_with_its_role() -> None:
    """An active account tells its role."""
    api, user_id = await _stored(active=True)

    assert await api.role_of(user_id) is Role.TEACHER


async def test_a_deactivated_account_answers_with_nothing() -> None:
    """A turned-off account does not act, like a missing one."""
    api, user_id = await _stored(active=False)

    assert await api.role_of(user_id) is None


async def test_a_missing_account_answers_with_nothing() -> None:
    """Cross-domain references have no foreign key; a dangling one is normal."""
    assert await AuthApiAdapter(FakeUserRepository()).role_of(uuid.uuid4()) is None
