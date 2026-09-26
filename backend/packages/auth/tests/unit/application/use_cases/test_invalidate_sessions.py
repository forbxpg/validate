"""Voiding every token of an account: the kill switch."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from auth_fakes import FakeAuditLog, FakeUnitOfWork, FakeUserRepository, FrozenClock

from vld.auth.application import InvalidateSessions
from vld.auth.domain import AuthAuditAction, EntityNotFoundError, Role, User

NOW = datetime(2026, 9, 1, tzinfo=UTC)
_HASH = "hashed:pw"


def _stored(users: FakeUserRepository) -> User:
    user = User.register("user@example.test", _HASH, Role.STUDENT)
    users.items[user.id] = user
    return user


async def test_the_mark_is_set_and_committed() -> None:
    """The invalidation mark is set and committed."""
    users = FakeUserRepository()
    user = _stored(users)
    uow = FakeUnitOfWork()

    await InvalidateSessions(users, FrozenClock(now=NOW), FakeAuditLog(), uow)(
        user.id,
        actor_id=user.id,
    )

    stored = await users.get_by_id(user.id)
    assert stored is not None
    assert stored.tokens_invalidated_after is not None
    assert uow.committed is True


async def test_an_admin_reset_is_told_apart_by_the_actor() -> None:
    """The audit tells an own logout from a reset by an admin."""
    users = FakeUserRepository()
    user = _stored(users)
    admin_id = uuid.uuid4()
    audit = FakeAuditLog()

    await InvalidateSessions(
        users,
        FrozenClock(now=NOW),
        audit,
        FakeUnitOfWork(),
    )(user.id, actor_id=admin_id)

    entry = next(
        e for e in audit.entries if e.action is AuthAuditAction.SESSIONS_INVALIDATED
    )
    assert entry.actor_id == admin_id
    assert entry.target_id == user.id


async def test_nothing_is_written_for_an_unknown_account() -> None:
    """An unknown account leaves no trace."""
    audit = FakeAuditLog()
    uow = FakeUnitOfWork()

    with pytest.raises(EntityNotFoundError):
        await InvalidateSessions(
            FakeUserRepository(),
            FrozenClock(now=NOW),
            audit,
            uow,
        )(uuid.uuid4(), actor_id=uuid.uuid4())

    assert audit.entries == []
    assert uow.committed is False


async def test_repeating_the_reset_is_harmless() -> None:
    """Repeating the reset keeps the mark."""
    # The mark only moves forward, so a retry of a client that timed out is safe.
    users = FakeUserRepository()
    user = _stored(users)
    invalidate = InvalidateSessions(
        users,
        FrozenClock(now=NOW),
        FakeAuditLog(),
        FakeUnitOfWork(),
    )

    await invalidate(user.id, actor_id=user.id)
    after_first = await users.get_by_id(user.id)
    assert after_first is not None
    first = after_first.tokens_invalidated_after
    await invalidate(user.id, actor_id=user.id)

    after_second = await users.get_by_id(user.id)
    assert after_second is not None
    assert after_second.tokens_invalidated_after == first
