"""Confirming an address."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from auth_fakes import (
    GOOD_PASSWORD,
    NOW,
    PASSWORD_SETTINGS,
    FakeEmailSender,
    FakeHasher,
    FakeOutbox,
    FakeTokenRepository,
    FakeUnitOfWork,
    FakeUserRepository,
    FrozenClock,
    StaleReadTokenRepository,
    deliver_pending_verifications,
)
from pydantic import SecretStr

from vld.auth.application import (
    InvalidTokenError,
    RegisterCommand,
    RegisterUser,
    VerifyEmail,
)
from vld.auth.config import JwtSettings
from vld.auth.domain import (
    Role,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenPurpose,
    User,
    VerificationToken,
)

_SETTINGS = JwtSettings(secret_key=SecretStr("s" * 32))


@dataclass
class _Deps:
    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    tokens: FakeTokenRepository = field(default_factory=FakeTokenRepository)
    hasher: FakeHasher = field(default_factory=FakeHasher)
    email: FakeEmailSender = field(default_factory=FakeEmailSender)
    clock: FrozenClock = field(default_factory=FrozenClock)
    outbox: FakeOutbox = field(default_factory=FakeOutbox)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)

    def verify(self) -> VerifyEmail:
        return VerifyEmail(
            users=self.users,
            tokens=self.tokens,
            clock=self.clock,
            uow=self.uow,
        )

    async def register(self, email: str = "u@b.co") -> str:
        _ = await RegisterUser(
            users=self.users,
            hasher=self.hasher,
            outbox=self.outbox,
            uow=FakeUnitOfWork(),
            settings=PASSWORD_SETTINGS,
        )(
            RegisterCommand(
                email=email,
                password=GOOD_PASSWORD,
                role=Role.STUDENT,
            ),
        )
        await deliver_pending_verifications(
            self.outbox,
            self.users,
            self.tokens,
            self.email,
            self.clock,
        )
        return self.email.sent[-1][1]


def _unverify(deps: _Deps) -> None:
    # Only a hand-made row reaches this state: the domain never unconfirms.
    [user] = deps.users.items.values()
    deps.users.items[user.id] = User(
        id=user.id,
        email=user.email,
        email_verified_at=None,
        password_hash=user.password_hash,
        role=user.role,
        is_admin=user.is_admin,
        is_active=user.is_active,
    )


async def test_verify_confirms_the_address() -> None:
    """The token from the letter confirms the address."""
    deps = _Deps()
    raw = await deps.register()
    await deps.verify()(raw)

    user = next(iter(deps.users.items.values()))
    assert user.email_verified is True
    assert deps.uow.committed is True


async def test_unknown_token_is_rejected() -> None:
    """A token nobody issued is refused."""
    deps = _Deps()
    _ = await deps.register()
    with pytest.raises(InvalidTokenError):
        await deps.verify()(secrets.token_urlsafe(32))


async def test_expired_token_is_rejected() -> None:
    """An expired link is refused."""
    deps = _Deps()
    raw = await deps.register()
    deps.clock.advance(timedelta(hours=49))

    with pytest.raises(TokenExpiredError):
        await deps.verify()(raw)

    assert next(iter(deps.users.items.values())).email_verified is False


async def test_token_of_another_purpose_does_not_pass() -> None:
    """A reset token does not confirm an address."""
    deps = _Deps()
    raw = await deps.register()
    user = next(iter(deps.users.items.values()))

    reset_raw = secrets.token_urlsafe(32)
    await deps.tokens.add(
        VerificationToken.issue(
            user_id=user.id,
            token_hash=hashlib.sha256(reset_raw.encode()).hexdigest(),
            purpose=TokenPurpose.PASSWORD_RESET,
            now=NOW,
            ttl=timedelta(hours=1),
        ),
    )

    with pytest.raises(InvalidTokenError):
        await deps.verify()(reset_raw)

    untouched = await deps.users.get_by_id(user.id)
    assert untouched is not None
    assert untouched.email_verified is False
    assert deps.tokens.consumed == {}
    # The token works: its purpose is what was refused.
    await deps.verify()(raw)
    verified = await deps.users.get_by_id(user.id)
    assert verified is not None
    assert verified.email_verified is True


async def test_repeated_click_on_verified_account_is_success() -> None:
    """A second click on a working link is not an error."""
    deps = _Deps()
    raw = await deps.register()
    verify = deps.verify()
    await verify(raw)

    await verify(raw)  # does not raise

    assert next(iter(deps.users.items.values())).email_verified is True


async def test_used_token_on_unverified_address_is_rejected() -> None:
    """A used token of a still unconfirmed address is refused."""
    deps = _Deps()
    raw = await deps.register()
    await deps.verify()(raw)

    _unverify(deps)

    with pytest.raises(TokenAlreadyUsedError):
        await deps.verify()(raw)


async def test_concurrent_consume_records_only_the_winner() -> None:
    """Of two concurrent clicks only one consumes the token."""
    deps = _Deps(tokens=StaleReadTokenRepository())
    raw = await deps.register()
    verify = deps.verify()
    await verify(raw)

    deps.clock.advance(timedelta(minutes=5))
    await verify(raw)  # the loser of the race is a successful no-op

    assert deps.tokens.consumed == {1: NOW}


async def test_lost_race_on_unverified_address_raises() -> None:
    """The loser of the race raises while the address is unconfirmed."""
    deps = _Deps(tokens=StaleReadTokenRepository())
    raw = await deps.register()
    await deps.verify()(raw)

    _unverify(deps)

    with pytest.raises(TokenAlreadyUsedError):
        await deps.verify()(raw)


async def test_nothing_is_committed_when_token_owner_is_gone() -> None:
    """A token whose account is gone commits nothing."""
    deps = _Deps()
    raw = await deps.register()
    deps.users.items.clear()

    with pytest.raises(InvalidTokenError):
        await deps.verify()(raw)

    assert deps.uow.committed is False
    assert deps.tokens.consumed == {}
