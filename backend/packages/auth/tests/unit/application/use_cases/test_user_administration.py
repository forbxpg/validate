"""Administration of accounts: listing, access, roles, admin rights, deletion."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest
from auth_fakes import (
    NOW,
    FakeAuditLog,
    FakeAuditQuery,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
)

from vld.auth.application import (
    ChangeUserRole,
    DeleteUser,
    GetUser,
    GrantAdmin,
    ListUsers,
    ReadAudit,
    SetUserActive,
    TargetForbiddenError,
)
from vld.auth.domain import Role, User, UserNotFoundError
from vld.core.audit import AuditAction


def _user(
    email: str = "s@b.co",
    *,
    role: Role = Role.STUDENT,
    is_admin: bool = False,
    is_active: bool = True,
) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        email_verified_at=NOW,
        password_hash="hashed:pw",
        role=role,
        is_admin=is_admin,
        is_active=is_active,
    )


@dataclass
class _Deps:
    """Fakes shared by the use cases."""

    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)
    audit: FakeAuditLog = field(default_factory=FakeAuditLog)
    clock: FrozenClock = field(default_factory=FrozenClock)
    admin: User = field(default_factory=lambda: _user("admin@b.co", is_admin=True))

    async def store(self, user: User) -> User:
        """Store an account and return it."""
        await self.users.add(user)
        return user

    def set_active(self) -> SetUserActive:
        """Build turning accounts off and on."""
        return SetUserActive(self.users, self.clock, self.uow, self.audit)

    def change_role(self) -> ChangeUserRole:
        """Build the role change."""
        return ChangeUserRole(self.users, self.uow, self.audit)


async def test_list_users_filters_and_pages() -> None:
    """The list applies the filters and counts all matches."""
    deps = _Deps()
    for index in range(3):
        _ = await deps.store(_user(f"s{index}@b.co"))
    _ = await deps.store(_user("t@b.co", role=Role.TEACHER))
    _ = await deps.store(_user("off@b.co", is_active=False))

    page = await ListUsers(deps.users)(
        role=Role.STUDENT,
        is_active=True,
        limit=2,
        offset=0,
    )

    assert page.total == 3
    assert len(page.users) == 2
    assert all(user.role is Role.STUDENT and user.is_active for user in page.users)


async def test_get_user_of_an_unknown_id_is_not_found() -> None:
    """An unknown id is a 404, not a defect."""
    with pytest.raises(UserNotFoundError):
        _ = await GetUser(FakeUserRepository())(uuid.uuid4())


async def test_deactivation_ends_the_sessions_and_is_audited() -> None:
    """Turning an account off voids its tokens and leaves a record."""
    deps = _Deps()
    target = await deps.store(_user())

    user = await deps.set_active()(target.id, active=False, actor_id=deps.admin.id)

    assert not user.is_active
    stored = await deps.users.get_by_id(target.id)
    assert stored is not None
    assert not stored.is_active
    assert stored.tokens_invalidated_after is not None
    [entry] = deps.audit.entries
    assert entry.action is AuditAction.USER_DEACTIVATED
    assert (entry.actor_id, entry.target_id) == (deps.admin.id, target.id)
    assert deps.uow.committed


async def test_activation_restores_access_and_is_audited() -> None:
    """Turning an account back on is recorded too."""
    deps = _Deps()
    target = await deps.store(_user(is_active=False))

    user = await deps.set_active()(target.id, active=True, actor_id=deps.admin.id)

    assert user.is_active
    assert [entry.action for entry in deps.audit.entries] == [
        AuditAction.USER_ACTIVATED,
    ]


@pytest.mark.parametrize("target_is", ["self", "another-admin"])
async def test_an_admin_cannot_act_on_self_or_another_admin(target_is: str) -> None:
    """Admins are managed from the console only."""
    deps = _Deps()
    _ = await deps.store(deps.admin)
    target = (
        deps.admin
        if target_is == "self"
        else await deps.store(_user("other@b.co", is_admin=True))
    )

    with pytest.raises(TargetForbiddenError):
        _ = await deps.set_active()(target.id, active=False, actor_id=deps.admin.id)
    with pytest.raises(TargetForbiddenError):
        _ = await deps.change_role()(deps.admin.id, target.id, Role.TEACHER)

    stored = await deps.users.get_by_id(target.id)
    assert stored is not None
    assert stored.is_active
    assert deps.audit.entries == []
    assert not deps.uow.committed


async def test_set_active_of_an_unknown_account_is_not_found() -> None:
    """An unknown id is refused before anything is written."""
    deps = _Deps()

    with pytest.raises(UserNotFoundError):
        _ = await deps.set_active()(uuid.uuid4(), active=False, actor_id=deps.admin.id)

    assert deps.audit.entries == []


async def test_role_change_is_audited_with_both_roles() -> None:
    """The record says what the role was and what it became."""
    deps = _Deps()
    target = await deps.store(_user())

    user = await deps.change_role()(deps.admin.id, target.id, Role.TEACHER)

    assert user.role is Role.TEACHER
    [entry] = deps.audit.entries
    assert entry.action is AuditAction.USER_ROLE_CHANGED
    assert entry.payload == {"from": "student", "to": "teacher"}


async def test_the_same_role_changes_nothing() -> None:
    """Setting the current role writes no record."""
    deps = _Deps()
    target = await deps.store(_user())

    _ = await deps.change_role()(deps.admin.id, target.id, Role.STUDENT)

    assert deps.audit.entries == []


async def test_grant_admin_sets_the_flag_once() -> None:
    """The console grants admin rights once and records it."""
    deps = _Deps()
    target = await deps.store(_user())
    grant = GrantAdmin(deps.users, deps.uow, deps.audit)

    _ = await grant("S@B.co")
    user = await grant("s@b.co")

    assert user.is_admin
    assert [entry.action for entry in deps.audit.entries] == [AuditAction.ADMIN_GRANTED]
    assert deps.audit.entries[0].target_id == target.id
    assert deps.audit.entries[0].actor_id is None


async def test_grant_admin_to_an_unknown_address_is_not_found() -> None:
    """Admin rights go only to a registered account."""
    deps = _Deps()

    with pytest.raises(UserNotFoundError):
        _ = await GrantAdmin(deps.users, deps.uow, deps.audit)("nobody@b.co")


async def test_delete_user_removes_the_row_and_keeps_only_the_id() -> None:
    """The personal data leaves with the row; the audit keeps the id alone."""
    deps = _Deps()
    target = await deps.store(_user())

    await DeleteUser(deps.users, deps.uow, deps.audit)("s@b.co")

    assert await deps.users.get_by_id(target.id) is None
    [entry] = deps.audit.entries
    assert entry.action is AuditAction.USER_DELETED
    assert entry.target_id == target.id
    assert entry.payload == {}
    assert deps.uow.committed


async def test_delete_of_an_unknown_address_is_not_found() -> None:
    """Deleting a missing account is an error, not a quiet success."""
    deps = _Deps()

    with pytest.raises(UserNotFoundError):
        await DeleteUser(deps.users, deps.uow, deps.audit)("nobody@b.co")

    assert deps.audit.entries == []


async def test_read_audit_passes_the_filters() -> None:
    """The reader returns the records of the asked target, newest first."""
    log = FakeAuditLog()
    deps = _Deps(audit=log)
    first = await deps.store(_user("a@b.co"))
    second = await deps.store(_user("b@b.co"))
    _ = await deps.change_role()(deps.admin.id, first.id, Role.TEACHER)
    _ = await deps.change_role()(deps.admin.id, second.id, Role.TEACHER)

    page = await ReadAudit(FakeAuditQuery(log))(
        actor_id=None,
        target_id=second.id,
        occurred_from=None,
        occurred_to=None,
        limit=10,
        offset=0,
    )

    assert page.total == 1
    assert page.records[0].target_id == second.id
