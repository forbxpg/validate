"""Describing the logged-in user."""

from __future__ import annotations

import uuid

import pytest
from auth_fakes import NOW, FakeUserRepository

from vld.auth.application import DescribeMe, MeView
from vld.auth.domain import EntityNotFoundError, Profile, Role, User


async def test_describes_the_user_behind_the_token() -> None:
    """The view carries the account, role, rights and profile."""
    users = FakeUserRepository()
    profile = Profile(first_name_ru="Иван")
    user = User.register("user@example.test", "hashed:pw", Role.TEACHER, profile)
    user.verify_email(NOW)
    await users.add(user)

    view = await DescribeMe(users)(user.id)

    assert view == MeView(
        user_id=user.id,
        email="user@example.test",
        email_verified=True,
        role=Role.TEACHER,
        is_admin=False,
        profile=profile,
    )


async def test_a_missing_row_is_a_defect_not_an_outcome() -> None:
    """A valid token without its row is a store defect."""
    # A valid token without its row is a store defect, hence 500.
    with pytest.raises(EntityNotFoundError):
        _ = await DescribeMe(FakeUserRepository())(uuid.uuid4())
