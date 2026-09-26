"""Sending the confirmation letter again."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from auth_fakes import (
    NOW,
    CountingLimiter,
    FakeOutbox,
    FakeUnitOfWork,
    FakeUserRepository,
)

from vld.auth.application import ResendVerification, ResendVerificationCommand
from vld.auth.domain import Role, User
from vld.core.ratelimit import RateLimitExceededError

_HASH = "hashed:pw"


@dataclass
class _Deps:
    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    outbox: FakeOutbox = field(default_factory=FakeOutbox)
    limiter: CountingLimiter = field(default_factory=CountingLimiter)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)

    def use_case(self) -> ResendVerification:
        return ResendVerification(self.users, self.outbox, self.limiter, self.uow)


async def _seed(deps: _Deps, email: str, *, verified: bool) -> User:
    user = User.register(email, _HASH, Role.STUDENT)
    if verified:
        user.verify_email(NOW)
    # Drop the registration event to see only what the resend writes.
    _ = user.pull_events()
    await deps.users.add(user)
    return user


async def test_an_unverified_address_gets_exactly_one_event() -> None:
    """An unconfirmed address gets exactly one registration event."""
    deps = _Deps()
    user = await _seed(deps, "pending@b.co", verified=False)

    await deps.use_case()(ResendVerificationCommand(email="pending@b.co"))

    assert deps.uow.committed is True
    assert [event.name for event in deps.outbox.events] == ["auth.user_registered"]
    assert deps.outbox.events[0].payload["user_id"] == str(user.id)


async def test_an_unknown_address_writes_nothing() -> None:
    """An unknown address writes nothing."""
    deps = _Deps()

    await deps.use_case()(ResendVerificationCommand(email="nobody@b.co"))

    assert deps.outbox.events == []
    assert deps.uow.committed is False


async def test_a_verified_address_writes_nothing() -> None:
    """A confirmed address has nothing to resend."""
    deps = _Deps()
    _ = await _seed(deps, "done@b.co", verified=True)

    await deps.use_case()(ResendVerificationCommand(email="done@b.co"))

    assert deps.outbox.events == []


async def test_letters_to_one_address_are_limited() -> None:
    """Letters to one address are limited, whatever its case."""
    deps = _Deps()
    _ = await _seed(deps, "pending@b.co", verified=False)
    resend = deps.use_case()

    for _attempt in range(3):
        await resend(ResendVerificationCommand(email="Pending@B.co"))
    with pytest.raises(RateLimitExceededError):
        await resend(ResendVerificationCommand(email="pending@b.co"))

    # The bucket key hides the address: the limiter store is not a mailing list.
    assert all("pending@b.co" not in key for key in deps.limiter.keys)
    assert len(deps.outbox.events) == 3
