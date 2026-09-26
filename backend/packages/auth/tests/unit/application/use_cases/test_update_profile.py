"""Replacing the personal details of the own account."""

from __future__ import annotations

import uuid

import pytest
from auth_fakes import FakeUnitOfWork, FakeUserRepository

from vld.auth.application import UpdateProfile
from vld.auth.domain import EntityNotFoundError, Profile, Role, User


async def test_the_profile_is_replaced_whole() -> None:
    """A field left out of the new profile is cleared."""
    users = FakeUserRepository()
    user = User.register(
        "u@b.co",
        "hashed:pw",
        Role.STUDENT,
        Profile(first_name_ru="Иван"),
    )
    await users.add(user)
    uow = FakeUnitOfWork()

    profile = await UpdateProfile(users, uow)(user.id, Profile(last_name_en="Ivanov"))

    assert profile == Profile(last_name_en="Ivanov")
    stored = await users.get_by_id(user.id)
    assert stored is not None
    assert stored.profile == Profile(last_name_en="Ivanov")
    assert uow.committed


async def test_an_unknown_account_is_a_defect() -> None:
    """A valid token without its row is a store defect."""
    with pytest.raises(EntityNotFoundError):
        _ = await UpdateProfile(FakeUserRepository(), FakeUnitOfWork())(
            uuid.uuid4(),
            Profile(),
        )
