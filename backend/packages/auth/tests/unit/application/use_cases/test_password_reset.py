"""Password reset: asking for the letter and setting a password by its link."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from auth_fakes import (
    GOOD_PASSWORD,
    NOW,
    PASSWORD_SETTINGS,
    CountingLimiter,
    FakeAuditLog,
    FakeEmailSender,
    FakeHasher,
    FakeOutbox,
    FakeTokenRepository,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
    StaleReadTokenRepository,
    deliver_pending_password_resets,
)
from pydantic import SecretStr

from vld.auth.application import (
    InvalidTokenError,
    RequestPasswordReset,
    ResetPassword,
    SendPasswordResetEmail,
    WeakPasswordError,
)
from vld.auth.application.use_cases.shared._email_verification import (
    issue_verification,
)
from vld.auth.application.use_cases.shared._token_hashing import hash_token
from vld.auth.config import JwtSettings
from vld.auth.domain import (
    PASSWORD_RESET_REQUESTED_EVENT,
    DomainEvent,
    Role,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenPurpose,
    User,
)
from vld.core.audit import AuditAction
from vld.core.ratelimit import RateLimitExceededError

_SETTINGS = JwtSettings(secret_key=SecretStr("s" * 32))
_OLD_HASH = "hashed:old password"
_NEW_PASSWORD = "Totally New Passphrase"


@dataclass
class _Deps:
    """Fakes and the use cases built on them."""

    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    tokens: FakeTokenRepository = field(default_factory=FakeTokenRepository)
    hasher: FakeHasher = field(default_factory=FakeHasher)
    email: FakeEmailSender = field(default_factory=FakeEmailSender)
    outbox: FakeOutbox = field(default_factory=FakeOutbox)
    clock: FrozenClock = field(default_factory=FrozenClock)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)
    limiter: CountingLimiter = field(default_factory=CountingLimiter)
    audit: FakeAuditLog = field(default_factory=FakeAuditLog)

    def request(self) -> RequestPasswordReset:
        """Build the request for a reset letter."""
        return RequestPasswordReset(self.users, self.outbox, self.limiter, self.uow)

    def reset(self) -> ResetPassword:
        """Build the reset by link."""
        return ResetPassword(
            users=self.users,
            tokens=self.tokens,
            hasher=self.hasher,
            clock=self.clock,
            uow=self.uow,
            audit=self.audit,
            settings=PASSWORD_SETTINGS,
        )

    async def seed(self, email: str = "owner@b.co") -> User:
        """Store a confirmed account with a known password."""
        user = User.register(email=email, password_hash=_OLD_HASH, role=Role.STUDENT)
        user.verify_email(NOW)
        _ = user.pull_events()
        await self.users.add(user)
        return user

    async def deliver(self) -> str:
        """Drain the outbox through the handler and return the token from the letter."""
        await deliver_pending_password_resets(
            self.outbox,
            self.users,
            self.tokens,
            self.email,
            self.clock,
        )
        return self.email.reset_sent[-1][1]


async def test_existing_address_writes_one_reset_event() -> None:
    """A known address writes exactly one reset request."""
    deps = _Deps()
    user = await deps.seed()

    await deps.request()("owner@b.co")

    assert deps.uow.committed is True
    assert [event.name for event in deps.outbox.events] == [
        PASSWORD_RESET_REQUESTED_EVENT,
    ]
    assert deps.outbox.events[0].payload == {"user_id": str(user.id)}


async def test_unknown_address_writes_nothing() -> None:
    """An unknown address writes nothing."""
    deps = _Deps()
    _ = await deps.seed()

    await deps.request()("nobody@b.co")

    assert deps.outbox.events == []
    assert deps.uow.committed is False


async def test_request_returns_the_same_for_any_address() -> None:
    """Both outcomes look the same to the caller."""
    deps = _Deps()
    _ = await deps.seed()

    known = await deps.request()("owner@b.co")
    unknown = await deps.request()("nobody@b.co")

    assert known is None
    assert unknown is None


async def test_reset_changes_the_password_and_kills_sessions() -> None:
    """The link sets the password and ends every session."""
    deps = _Deps()
    user = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()

    await deps.reset()(raw_token, _NEW_PASSWORD)

    stored = await deps.users.get_by_id(user.id)
    assert stored is not None
    assert stored.password_hash is not None
    assert await deps.hasher.verify(_NEW_PASSWORD, stored.password_hash)
    assert stored.tokens_invalidated_after == NOW
    assert deps.uow.committed is True


async def test_a_spent_link_does_not_work_twice() -> None:
    """A second use of a worked link is an error, not a quiet success."""
    deps = _Deps()
    _ = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()
    await deps.reset()(raw_token, _NEW_PASSWORD)

    with pytest.raises(TokenAlreadyUsedError):
        await deps.reset()(raw_token, "Second Passphrase Entirely")


async def test_a_spent_link_leaves_the_first_password_in_place() -> None:
    """A refused spent link rewrites nothing."""
    deps = _Deps()
    user = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()
    await deps.reset()(raw_token, _NEW_PASSWORD)

    with pytest.raises(TokenAlreadyUsedError):
        await deps.reset()(raw_token, "Second Passphrase Entirely")

    stored = await deps.users.get_by_id(user.id)
    assert stored is not None
    assert stored.password_hash is not None
    assert await deps.hasher.verify(_NEW_PASSWORD, stored.password_hash)


async def test_a_concurrent_reset_loses_on_the_conditional_update() -> None:
    """Of two concurrent uses of one link only one wins."""
    deps = _Deps(tokens=StaleReadTokenRepository())
    _ = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()
    await deps.reset()(raw_token, _NEW_PASSWORD)

    with pytest.raises(TokenAlreadyUsedError):
        await deps.reset()(raw_token, "Second Passphrase Entirely")


async def test_a_new_reset_link_kills_the_previous_one() -> None:
    """A second letter voids the first link and keeps its own."""
    deps = _Deps()
    user = await deps.seed()

    await deps.request()("owner@b.co")
    first = await deps.deliver()
    await deps.request()("owner@b.co")
    second = await deps.deliver()

    assert first != second, "the second request must issue another token"
    with pytest.raises(TokenAlreadyUsedError):
        await deps.reset()(first, _NEW_PASSWORD)

    await deps.reset()(second, _NEW_PASSWORD)
    stored = await deps.users.get_by_id(user.id)
    assert stored is not None
    assert stored.password_hash is not None
    assert await deps.hasher.verify(_NEW_PASSWORD, stored.password_hash)


async def test_a_new_reset_link_leaves_the_verification_link_alone() -> None:
    """Rotating the reset link leaves the confirmation link alone."""
    deps = _Deps()
    user = await deps.seed()
    _, verification = issue_verification(user.id, NOW)
    await deps.tokens.add(verification)

    await deps.request()("owner@b.co")
    _ = await deps.deliver()

    survived = await deps.tokens.get_by_hash(
        verification.token_hash,
        TokenPurpose.EMAIL_VERIFY,
    )
    assert survived is not None
    survived.consume(NOW)


async def test_a_retried_delivery_does_not_kill_its_own_link() -> None:
    """A retried outbox row does not void the link it sent."""
    users, tokens, email = (
        FakeUserRepository(),
        FakeTokenRepository(),
        FakeEmailSender(),
    )
    user = User.register(email="retry@b.co", password_hash=_OLD_HASH, role=Role.STUDENT)
    user.verify_email(NOW)
    _ = user.pull_events()
    await users.add(user)
    handler = SendPasswordResetEmail(users, tokens, email, FrozenClock(NOW), _SETTINGS)
    event = DomainEvent(PASSWORD_RESET_REQUESTED_EVENT, {"user_id": str(user.id)})

    _, first = await handler.prepare(event, 42)
    _, again = await handler.prepare(event, 42)

    assert first == again, "a retry must arrive at the same link"
    reissued = await tokens.get_by_hash(hash_token(again), TokenPurpose.PASSWORD_RESET)
    assert reissued is not None
    reissued.consume(NOW)


async def test_a_verification_token_is_not_a_reset_token() -> None:
    """A confirmation token does not reset a password."""
    deps = _Deps()
    user = await deps.seed()
    raw_token, token = issue_verification(user.id, NOW)
    await deps.tokens.add(token)

    with pytest.raises(InvalidTokenError):
        await deps.reset()(raw_token, _NEW_PASSWORD)

    stored = await deps.users.get_by_id(user.id)
    assert stored is not None
    assert stored.password_hash == _OLD_HASH


async def test_an_unknown_token_is_rejected() -> None:
    """A made-up token is `InvalidTokenError`, not a 500 and not a success."""
    deps = _Deps()
    _ = await deps.seed()

    with pytest.raises(InvalidTokenError):
        await deps.reset()("no such token", _NEW_PASSWORD)


async def test_an_expired_link_is_rejected_as_expired() -> None:
    """An expired link is told apart from an unknown one."""
    deps = _Deps()
    _ = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()
    deps.clock.advance(timedelta(hours=2))

    with pytest.raises(TokenExpiredError):
        await deps.reset()(raw_token, _NEW_PASSWORD)


async def test_a_weak_password_is_rejected_before_the_link_is_spent() -> None:
    """A weak password is refused without burning the link."""
    deps = _Deps()
    _ = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()

    with pytest.raises(WeakPasswordError):
        await deps.reset()(raw_token, "123456")

    await deps.reset()(raw_token, GOOD_PASSWORD)


async def test_a_rejected_weak_password_is_never_hashed() -> None:
    """A refusal by the rules never reaches the hasher."""
    deps = _Deps()
    _ = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()

    with pytest.raises(WeakPasswordError):
        await deps.reset()(raw_token, "123456")

    assert deps.hasher.hashed == []


async def test_reset_token_is_stored_with_its_own_purpose() -> None:
    """The handler stores the token as a reset token."""
    deps = _Deps()
    _ = await deps.seed()
    await deps.request()("owner@b.co")
    raw_token = await deps.deliver()

    found = await deps.tokens.get_by_hash(
        hash_token(raw_token),
        TokenPurpose.PASSWORD_RESET,
    )

    assert found is not None


async def test_a_reset_confirms_the_address_and_is_audited() -> None:
    """The link proves the mailbox: the address is confirmed and the audit knows."""
    deps = _Deps()
    user = User.register("squatted@b.co", _OLD_HASH, Role.STUDENT)
    _ = user.pull_events()
    await deps.users.add(user)
    await deps.request()("squatted@b.co")
    raw_token = await deps.deliver()

    await deps.reset()(raw_token, _NEW_PASSWORD)

    stored = await deps.users.get_by_id(user.id)
    assert stored is not None
    assert stored.email_verified
    assert [entry.action for entry in deps.audit.entries] == [
        AuditAction.PASSWORD_RESET,
    ]
    assert deps.audit.entries[0].actor_id == user.id


async def test_reset_letters_to_one_address_are_limited() -> None:
    """A fourth request within the hour is refused, whatever the case of the address."""
    deps = _Deps()
    _ = await deps.seed()
    request = deps.request()

    for _attempt in range(3):
        await request("Owner@B.co")
    with pytest.raises(RateLimitExceededError):
        await request("owner@b.co")
