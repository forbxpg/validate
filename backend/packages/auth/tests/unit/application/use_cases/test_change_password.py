"""Changing the password while logged in."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from auth_fakes import (
    GOOD_PASSWORD,
    NOW,
    PASSWORD_SETTINGS,
    FakeAuditLog,
    FakeHasher,
    FakeTokenIssuer,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
)

from vld.auth.application import (
    ChangePassword,
    ChangePasswordCommand,
    WeakPasswordError,
)
from vld.auth.domain import InvalidCredentialsError, Role, User
from vld.core.audit import AuditAction

_NEW_PASSWORD = "Brand New Passphrase"


@dataclass
class _Deps:
    """Fakes and the use case built on them."""

    clock: FrozenClock = field(
        default_factory=lambda: FrozenClock(NOW + timedelta(milliseconds=250)),
    )
    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    hasher: FakeHasher = field(default_factory=FakeHasher)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)
    audit: FakeAuditLog = field(default_factory=FakeAuditLog)
    issuer: FakeTokenIssuer = field(init=False)

    def __post_init__(self) -> None:
        """Share the clock with the issuer."""
        self.issuer = FakeTokenIssuer(clock=self.clock)

    def use_case(self) -> ChangePassword:
        """Build the use case on these fakes."""
        return ChangePassword(
            users=self.users,
            hasher=self.hasher,
            issuer=self.issuer,
            clock=self.clock,
            uow=self.uow,
            audit=self.audit,
            settings=PASSWORD_SETTINGS,
        )

    async def seed(self) -> User:
        """Store an account with a known password."""
        user = User.register("u@b.co", f"hashed:{GOOD_PASSWORD}", Role.STUDENT)
        _ = user.pull_events()
        await self.users.add(user)
        return user


def _command(user: User, current: str = GOOD_PASSWORD) -> ChangePasswordCommand:
    return ChangePasswordCommand(
        user_id=user.id,
        current_password=current,
        new_password=_NEW_PASSWORD,
    )


async def test_the_change_ends_other_sessions_and_keeps_this_one() -> None:
    """Old tokens are void; the new pair is not."""
    deps = _Deps()
    user = await deps.seed()
    old_access, _ = deps.issuer.issue_pair(user.id)

    pair = await deps.use_case()(_command(user))

    stored = await deps.users.get_by_id(user.id)
    assert stored is not None
    mark = stored.tokens_invalidated_after
    assert mark is not None
    assert stored.password_hash == f"hashed:{_NEW_PASSWORD}"
    assert deps.issuer.parse_access(old_access).issued_at < mark
    assert deps.issuer.parse_access(pair.access).issued_at >= mark
    assert deps.issuer.parse_refresh(pair.refresh).issued_at >= mark
    assert [entry.action for entry in deps.audit.entries] == [
        AuditAction.PASSWORD_CHANGED,
    ]


async def test_a_wrong_current_password_changes_nothing() -> None:
    """The current password must match."""
    deps = _Deps()
    user = await deps.seed()

    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(_command(user, current="Not The Password"))

    stored = await deps.users.get_by_id(user.id)
    assert stored is not None
    assert stored.password_hash == f"hashed:{GOOD_PASSWORD}"
    assert deps.audit.entries == []


async def test_a_weak_new_password_is_refused_before_hashing() -> None:
    """The rules run before any hashing."""
    deps = _Deps()
    user = await deps.seed()

    with pytest.raises(WeakPasswordError):
        _ = await deps.use_case()(
            ChangePasswordCommand(
                user_id=user.id,
                current_password=GOOD_PASSWORD,
                new_password="short",
            ),
        )

    assert deps.hasher.verified == []
    assert deps.hasher.hashed == []


async def test_an_unknown_account_is_a_defect() -> None:
    """A valid token without its row is a store defect."""
    deps = _Deps()

    with pytest.raises(Exception, match="does not exist"):
        _ = await deps.use_case()(
            ChangePasswordCommand(
                user_id=uuid.uuid4(),
                current_password=GOOD_PASSWORD,
                new_password=_NEW_PASSWORD,
            ),
        )
