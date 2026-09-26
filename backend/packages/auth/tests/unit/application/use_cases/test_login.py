"""Logging in with a password."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, override

import pytest
from auth_fakes import (
    ALLOW_UNVERIFIED,
    GOOD_PASSWORD,
    NOW,
    REQUIRE_VERIFIED,
    AllowAllLimiter,
    AuditWriteFailedError,
    CountingLimiter,
    DenyAllLimiter,
    FailingAuditLog,
    FakeAuditLog,
    FakeHasher,
    FakeTokenIssuer,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
)

from vld.auth.application import (
    LoginCommand,
    LoginWithPassword,
)
from vld.auth.application.use_cases.session._login import _EMAIL_LIMIT
from vld.auth.domain import (
    AccountDeactivatedError,
    AuthAuditAction,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    Role,
    User,
)
from vld.core.ratelimit import RateLimitExceededError

if TYPE_CHECKING:
    from vld.auth.application import RateLimiter
    from vld.auth.config import VerificationSettings

_EMAIL = "u@b.co"
_WRONG_PASSWORD = "Wrong Pass Here"


def _user(
    *,
    verified: bool = True,
    active: bool = True,
    email: str = _EMAIL,
    password_hash: str = f"hashed:{GOOD_PASSWORD}",
) -> User:
    """Build an account in the wanted state, skipping registration."""
    return User(
        id=uuid.uuid4(),
        email=email,
        email_verified_at=NOW if verified else None,
        password_hash=password_hash,
        role=Role.STUDENT,
        is_admin=False,
        is_active=active,
    )


@dataclass
class _Deps:
    """Fakes and the use case built on them."""

    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    hasher: FakeHasher = field(default_factory=FakeHasher)
    issuer: FakeTokenIssuer = field(default_factory=FakeTokenIssuer)
    limiter: RateLimiter = field(default_factory=AllowAllLimiter)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)
    audit: FakeAuditLog = field(default_factory=FakeAuditLog)
    verification: VerificationSettings = REQUIRE_VERIFIED

    def use_case(self) -> LoginWithPassword:
        """Build the use case on these fakes."""
        return LoginWithPassword(
            users=self.users,
            hasher=self.hasher,
            issuer=self.issuer,
            limiter=self.limiter,
            uow=self.uow,
            audit=self.audit,
            verification=self.verification,
        )

    async def store(self, user: User) -> User:
        """Store an account and return it."""
        await self.users.add(user)
        return user


def _command(
    email: str = _EMAIL,
    password: str = GOOD_PASSWORD,
    device_token: str | None = None,
) -> LoginCommand:
    return LoginCommand(email=email, password=password, device_token=device_token)


def _sha256(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()


async def test_active_account_gets_a_token_pair() -> None:
    """A confirmed active account gets a pair of its own."""
    deps = _Deps()
    user = await deps.store(_user())

    result = await deps.use_case()(_command())

    assert deps.issuer.parse_access(result.pair.access).user_id == user.id
    assert deps.issuer.parse_refresh(result.pair.refresh).user_id == user.id


@pytest.mark.parametrize(
    ("stored", "command"),
    [
        pytest.param(None, _command(email="nobody@b.co"), id="unknown-email"),
        pytest.param(_user(), _command(password=_WRONG_PASSWORD), id="wrong-password"),
    ],
)
async def test_password_is_always_verified(
    stored: User | None,
    command: LoginCommand,
) -> None:
    """Every failing path checks a password, so timing reveals no address."""
    deps = _Deps()
    if stored is not None:
        _ = await deps.store(stored)

    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(command)

    assert len(deps.hasher.verified) == 1, "verify must run exactly once"
    checked_password, checked_hash = deps.hasher.verified[0]
    assert checked_password == command.password
    assert checked_hash, "the check needs a real hash"


async def test_unknown_email_and_wrong_password_look_identical() -> None:
    """An unknown address and a wrong password give the same answer."""
    deps = _Deps()
    _ = await deps.store(_user())
    login = deps.use_case()

    with pytest.raises(InvalidCredentialsError) as wrong_password:
        _ = await login(_command(password=_WRONG_PASSWORD))
    with pytest.raises(InvalidCredentialsError) as unknown_email:
        _ = await login(_command(email="nobody@b.co", password=_WRONG_PASSWORD))

    assert str(wrong_password.value) == str(unknown_email.value)
    assert type(wrong_password.value) is type(unknown_email.value)


@pytest.mark.parametrize(
    "stored",
    [_user(verified=False), _user(active=False)],
    ids=["unverified", "deactivated"],
)
async def test_the_state_is_not_revealed_before_the_password_matches(
    stored: User,
) -> None:
    """A wrong password gets the common error whatever the account state."""
    deps = _Deps()
    _ = await deps.store(stored)

    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(_command(password=_WRONG_PASSWORD))


async def test_an_unverified_address_is_told_to_confirm_it() -> None:
    """The right password on an unconfirmed address is its own error."""
    deps = _Deps()
    _ = await deps.store(_user(verified=False))

    with pytest.raises(EmailNotVerifiedError):
        _ = await deps.use_case()(_command())


async def test_an_unverified_address_logs_in_when_the_setting_allows() -> None:
    """With the check off an unconfirmed address logs in."""
    deps = _Deps(verification=ALLOW_UNVERIFIED)
    _ = await deps.store(_user(verified=False))

    result = await deps.use_case()(_command())

    assert result.pair.access


async def test_a_deactivated_account_is_told_so() -> None:
    """A deactivated account hears it after the right password."""
    deps = _Deps()
    _ = await deps.store(_user(active=False))

    with pytest.raises(AccountDeactivatedError):
        _ = await deps.use_case()(_command())


async def test_a_login_after_logout_everywhere_gets_a_working_pair() -> None:
    """A pair issued in the second of the kill switch is not void at birth."""
    # Mid-second: the mark rounds up past the second the pair would carry.
    clock = FrozenClock(NOW + timedelta(milliseconds=250))
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock))
    user = _user()
    user.invalidate_tokens(clock.now())
    _ = await deps.store(user)

    result = await deps.use_case()(_command())

    mark = user.tokens_invalidated_after
    assert mark is not None
    assert deps.issuer.parse_access(result.pair.access).issued_at >= mark
    assert deps.issuer.parse_refresh(result.pair.refresh).issued_at >= mark


async def test_rate_limit_is_checked_before_hashing() -> None:
    """The limiter runs before the hasher."""
    deps = _Deps(limiter=DenyAllLimiter())
    _ = await deps.store(_user())

    with pytest.raises(RateLimitExceededError):
        _ = await deps.use_case()(_command())

    assert deps.hasher.verified == [], "no hashing before the limit check"
    assert deps.hasher.hashed == []


async def test_email_bucket_blocks_the_sixth_attempt_in_the_window() -> None:
    """The per-address limit is five attempts in fifteen minutes."""
    limiter = CountingLimiter()  # the production limit, not overridden
    deps = _Deps(limiter=limiter)
    _ = await deps.store(_user())
    login = deps.use_case()

    for _attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))

    with pytest.raises(RateLimitExceededError):
        _ = await login(_command(password=_WRONG_PASSWORD))

    (bucket,) = set(limiter.keys)
    assert bucket.startswith("login:email:")
    assert limiter.windows[bucket] == 15 * 60_000


async def test_blocked_account_does_not_reset_its_own_bucket() -> None:
    """A refused account keeps its failed attempt on the count."""
    limiter = CountingLimiter()
    deps = _Deps(limiter=limiter)
    _ = await deps.store(_user(active=False))

    with pytest.raises(AccountDeactivatedError):
        _ = await deps.use_case()(_command())

    (bucket,) = set(limiter.keys)
    assert limiter.counts[bucket] == 1, "the refusal must stay on the count"


async def test_rate_limit_key_does_not_depend_on_account_existence() -> None:
    """A 429 must not tell whether an address is registered."""
    limiter = AllowAllLimiter()
    deps = _Deps(limiter=limiter)
    _ = await deps.store(_user())

    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(_command(password=_WRONG_PASSWORD))
    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(_command(email="NOBODY@b.co"))
    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(_command(email="nobody@b.co"))

    assert len(limiter.keys) == 3
    # The case of an address opens no bucket of its own.
    assert limiter.keys[1] == limiter.keys[2]
    assert all(_EMAIL not in key and "nobody" not in key for key in limiter.keys)


# ── Rehashing ───────────────────────────────────────────────────────────────


async def test_stale_hash_is_upgraded_after_successful_login() -> None:
    """Login is the only moment the plain password is at hand for a rehash."""
    deps = _Deps(hasher=FakeHasher(stale_prefix="v2:", generation="2"))
    user = await deps.store(_user())

    result = await deps.use_case()(_command())

    assert result.pair.access
    assert deps.users.password_hashes[user.id] == f"hashed2:{GOOD_PASSWORD}"
    assert deps.hasher.hashed == [GOOD_PASSWORD]


async def test_rehash_does_not_overwrite_a_concurrently_changed_password() -> None:
    """The conditional UPDATE keeps a password changed in another tab."""

    class _RacingRepository(FakeUserRepository):
        @override
        async def update_password_hash(
            self,
            user_id: uuid.UUID,
            expected_hash: str,
            new_hash: str,
        ) -> bool:
            # Another tab changed the password between the check and the write.
            self.password_hashes[user_id] = "hashed:brand new password"
            return await super().update_password_hash(
                user_id,
                expected_hash,
                new_hash,
            )

    deps = _Deps(
        users=_RacingRepository(),
        hasher=FakeHasher(stale_prefix="v2:", generation="2"),
    )
    user = await deps.store(_user())

    result = await deps.use_case()(_command())

    assert result.pair.access, "the login happened: its check already passed"
    assert deps.users.password_hashes[user.id] == "hashed:brand new password"


async def test_failed_rehash_does_not_fail_the_login() -> None:
    """A failed rehash write is logged and does not fail the login."""

    class _ExplodingRepository(FakeUserRepository):
        @override
        async def update_password_hash(
            self,
            user_id: uuid.UUID,
            expected_hash: str,
            new_hash: str,
        ) -> bool:
            del user_id, expected_hash, new_hash
            msg = "database is down"
            raise RuntimeError(msg)

    deps = _Deps(
        users=_ExplodingRepository(),
        hasher=FakeHasher(stale_prefix="v2:", generation="2"),
    )
    _ = await deps.store(_user())

    result = await deps.use_case()(_command())

    assert result.pair.access
    assert result.pair.refresh


async def test_fresh_hash_is_not_rewritten() -> None:
    """A current hash is left alone: no extra hashing per login."""
    deps = _Deps()
    _ = await deps.store(_user())

    _ = await deps.use_case()(_command())

    assert deps.hasher.hashed == []


async def test_successful_login_does_not_count_toward_the_lockout() -> None:
    """A successful login clears its bucket."""
    limiter = CountingLimiter(limit=1)
    deps = _Deps(limiter=limiter)
    _ = await deps.store(_user())
    login = deps.use_case()

    for _attempt in range(3):
        result = await login(_command())
        assert result.pair.access

    assert limiter.counts == {}, "the bucket must be empty after a success"


async def test_failed_logins_still_accumulate() -> None:
    """Failed attempts still add up."""
    limiter = CountingLimiter(limit=1)
    deps = _Deps(limiter=limiter)
    _ = await deps.store(_user())
    login = deps.use_case()

    with pytest.raises(InvalidCredentialsError):
        _ = await login(_command(password=_WRONG_PASSWORD))
    with pytest.raises(RateLimitExceededError):
        _ = await login(_command(password=_WRONG_PASSWORD))


async def test_surrounding_whitespace_finds_the_same_account() -> None:
    """Surrounding whitespace finds the same account."""
    deps = _Deps()
    user = await deps.store(_user(email="  u@b.co  "))
    assert user.email == "u@b.co", "the aggregate keeps the normalized address"

    result = await deps.use_case()(_command(email="\tu@b.co\n"))

    assert deps.issuer.parse_access(result.pair.access).user_id == user.id


# ── Device marker: bypasses the address bucket for its own account only ─────


async def test_login_issues_a_device_marker_bound_to_the_account() -> None:
    """A login issues a device marker bound to the account."""
    deps = _Deps()
    user = await deps.store(_user())

    result = await deps.use_case()(_command())

    assert deps.issuer.parse_device(result.device).user_id == user.id


async def test_device_marker_bypasses_the_email_bucket_for_its_own_account() -> None:
    """A spent bucket does not lock out the owner of a marker."""
    deps = _Deps(limiter=CountingLimiter())
    user = await deps.store(_user())
    device = deps.issuer.issue_device(user.id)
    login = deps.use_case()

    for _attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))
    with pytest.raises(RateLimitExceededError):
        _ = await login(_command())

    result = await login(_command(device_token=device))

    assert result.pair.access


async def test_device_marker_of_account_a_does_not_bypass_the_bucket_of_b() -> None:
    """The marker of account A does not bypass the bucket of account B."""
    deps = _Deps(limiter=CountingLimiter())
    _ = await deps.store(_user())
    attacker = await deps.store(_user(email="attacker@b.co"))
    device = deps.issuer.issue_device(attacker.id)
    login = deps.use_case()

    for _attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))

    with pytest.raises(RateLimitExceededError):
        _ = await login(_command(device_token=device))


async def test_a_marker_issued_before_the_kill_switch_does_not_bypass() -> None:
    """The kill switch voids device markers too, not only refresh tokens."""
    deps = _Deps(limiter=CountingLimiter())
    user = await deps.store(_user())
    device = deps.issuer.issue_device(user.id)
    # A second is the smallest step: iat of a JWT is in whole seconds.
    user.invalidate_tokens(NOW + timedelta(seconds=1))
    await deps.users.update(user)
    login = deps.use_case()

    for _attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))

    with pytest.raises(RateLimitExceededError):
        _ = await login(_command(device_token=device))


async def test_a_marker_issued_after_the_kill_switch_still_bypasses() -> None:
    """A marker issued after "log out everywhere" bypasses again."""
    clock = FrozenClock()
    deps = _Deps(issuer=FakeTokenIssuer(clock=clock), limiter=CountingLimiter())
    user = await deps.store(_user())
    user.invalidate_tokens(clock.now())
    clock.advance(timedelta(seconds=5))
    device = deps.issuer.issue_device(user.id)
    login = deps.use_case()

    for _attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))

    result = await login(_command(device_token=device))

    assert result.pair.access


async def test_a_password_change_does_not_revoke_the_device_marker() -> None:
    """A password change keeps the device marker, by decision."""
    new_password = "Brand New Passphrase"
    deps = _Deps(limiter=CountingLimiter())
    user = await deps.store(_user())
    device = deps.issuer.issue_device(user.id)
    # A new hash of the same account; the kill switch is untouched.
    await deps.users.update(
        User(
            id=user.id,
            email=user.email,
            email_verified_at=NOW,
            password_hash=f"hashed:{new_password}",
            role=Role.STUDENT,
            is_admin=False,
            is_active=True,
        ),
    )
    login = deps.use_case()

    for _attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))

    result = await login(_command(password=new_password, device_token=device))

    assert result.pair.access


async def test_a_refresh_token_is_not_a_device_marker() -> None:
    """A refresh token is not a device marker."""
    deps = _Deps(limiter=CountingLimiter())
    user = await deps.store(_user())
    _, refresh = deps.issuer.issue_pair(user.id)
    login = deps.use_case()

    for _attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))

    with pytest.raises(RateLimitExceededError):
        _ = await login(_command(device_token=refresh))


# ── Guards of the fakes themselves ──────────────────────────────────────────


async def test_allow_all_limiter_really_allows_all() -> None:
    """`AllowAllLimiter` never refuses."""
    limiter = AllowAllLimiter()
    deps = _Deps(limiter=limiter)
    _ = await deps.store(_user())
    login = deps.use_case()

    for _attempt in range(_EMAIL_LIMIT * 2):
        with pytest.raises(InvalidCredentialsError):
            _ = await login(_command(password=_WRONG_PASSWORD))

    assert len(limiter.keys) == _EMAIL_LIMIT * 2


async def test_fake_hasher_rejects_a_forged_hash() -> None:
    """The fake hasher refuses a forged `<anything>:<password>`."""
    hasher = FakeHasher()
    assert await hasher.verify(GOOD_PASSWORD, f"hashed:{GOOD_PASSWORD}") is True
    assert await hasher.verify(GOOD_PASSWORD, f"hashed7:{GOOD_PASSWORD}") is True
    assert await hasher.verify(GOOD_PASSWORD, f"forged:{GOOD_PASSWORD}") is False
    assert await hasher.verify(GOOD_PASSWORD, GOOD_PASSWORD) is False


async def test_successful_login_is_written_to_the_audit() -> None:
    """A login is a security event and goes to the audit."""
    deps = _Deps()
    user = await deps.store(_user())

    _ = await deps.use_case()(_command())

    assert [entry.action for entry in deps.audit.entries] == [
        AuthAuditAction.LOGIN_SUCCEEDED,
    ]
    assert deps.audit.entries[0].actor_id == user.id
    assert deps.uow.committed, "the audit entry was not committed"


async def test_failed_login_is_written_to_the_audit() -> None:
    """A failed login goes to the audit, with the address hashed."""
    deps = _Deps()
    _ = await deps.store(_user())

    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(_command(password=_WRONG_PASSWORD))

    assert [entry.action for entry in deps.audit.entries] == [
        AuthAuditAction.LOGIN_FAILED,
    ]
    assert deps.audit.entries[0].payload == {"email_sha256": _sha256(_EMAIL)}


async def test_login_by_an_unknown_address_is_recorded_without_an_actor() -> None:
    """An unknown address is recorded without an actor."""
    deps = _Deps()

    with pytest.raises(InvalidCredentialsError):
        _ = await deps.use_case()(_command(email="nobody@b.co"))

    assert [entry.action for entry in deps.audit.entries] == [
        AuthAuditAction.LOGIN_FAILED,
    ]
    assert deps.audit.entries[0].actor_id is None
    assert deps.audit.entries[0].payload == {"email_sha256": _sha256("nobody@b.co")}


async def test_a_deactivated_account_is_recorded_as_a_failed_login() -> None:
    """A refusal by account state is a failed login too."""
    deps = _Deps()
    _ = await deps.store(_user(active=False))

    with pytest.raises(AccountDeactivatedError):
        _ = await deps.use_case()(_command())

    assert [entry.action for entry in deps.audit.entries] == [
        AuthAuditAction.LOGIN_FAILED,
    ]


async def test_login_does_not_happen_when_the_audit_write_fails() -> None:
    """No audit entry, no login."""
    deps = _Deps()
    _ = await deps.store(_user())
    login = LoginWithPassword(
        users=deps.users,
        hasher=deps.hasher,
        issuer=deps.issuer,
        limiter=deps.limiter,
        uow=deps.uow,
        audit=FailingAuditLog(),
        verification=REQUIRE_VERIFIED,
    )

    with pytest.raises(AuditWriteFailedError):
        _ = await login(_command())

    assert not deps.uow.committed
    assert deps.uow.rolled_back
