"""Registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, override

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
    deliver_pending_verifications,
)
from pydantic import SecretStr

from vld.auth.application import (
    RegisterCommand,
    RegisterUser,
    WeakPasswordError,
)
from vld.auth.config import JwtSettings
from vld.auth.domain import EmailAlreadyTakenError, Profile, Role

if TYPE_CHECKING:
    from collections.abc import Sequence

    from vld.auth.domain import DomainEvent

_SETTINGS = JwtSettings(secret_key=SecretStr("s" * 32))
_GOOD_PASSWORD = GOOD_PASSWORD
_NOW = NOW


@dataclass
class _Deps:
    """Fakes and the use case built on them."""

    users: FakeUserRepository = field(default_factory=FakeUserRepository)
    tokens: FakeTokenRepository = field(default_factory=FakeTokenRepository)
    hasher: FakeHasher = field(default_factory=FakeHasher)
    email: FakeEmailSender = field(default_factory=FakeEmailSender)
    clock: FrozenClock = field(default_factory=FrozenClock)
    outbox: FakeOutbox = field(default_factory=FakeOutbox)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)

    def use_case(self) -> RegisterUser:
        """Build the use case on these fakes."""
        return RegisterUser(
            users=self.users,
            hasher=self.hasher,
            outbox=self.outbox,
            uow=self.uow,
            settings=PASSWORD_SETTINGS,
        )

    async def deliver(self) -> None:
        """Run the collected outbox through the handler, as the worker would."""
        await deliver_pending_verifications(
            self.outbox,
            self.users,
            self.tokens,
            self.email,
            self.clock,
        )


def _command(email: str, password: str = _GOOD_PASSWORD) -> RegisterCommand:
    return RegisterCommand(email=email, password=password, role=Role.STUDENT)


async def test_registration_writes_the_outbox_and_issues_nothing_inline() -> None:
    """Registration neither mails nor issues a token inline."""
    deps = _Deps()
    user_id = await deps.use_case()(_command("new@b.co"))

    user = deps.users.items[user_id]
    assert user.email_verified is False
    assert user.email_verified is False
    assert user.password_hash == f"hashed:{_GOOD_PASSWORD}"
    assert deps.uow.committed is True
    # No token and no letter on the request path: the worker handler issues them.
    assert deps.tokens.items == []
    assert deps.email.sent == []
    # Exactly one registration event in the outbox, with the account id.
    assert [event.name for event in deps.outbox.events] == ["auth.user_registered"]
    assert deps.outbox.events[0].payload["user_id"] == str(user_id)


async def test_the_worker_handler_issues_a_token_and_sends_the_email() -> None:
    """The letter and the token appear once the outbox is processed."""
    deps = _Deps()
    _ = await deps.use_case()(_command("new@b.co"))
    await deps.deliver()

    assert len(deps.tokens.items) == 1
    assert deps.email.sent[0][0] == "new@b.co"


async def test_token_is_stored_hashed() -> None:
    """The letter carries the token; the store keeps only its hash."""
    deps = _Deps()
    _ = await deps.use_case()(_command("h@b.co"))
    await deps.deliver()

    sent_token = deps.email.sent[0][1]
    stored = deps.tokens.items[0]
    assert sent_token
    assert stored.token_hash != sent_token
    assert sent_token not in stored.token_hash


async def test_token_expiry_comes_from_the_clock() -> None:
    """The expiry comes from the clock port, not from `datetime.now()`."""
    deps = _Deps()
    _ = await deps.use_case()(_command("t@b.co"))
    await deps.deliver()

    # Exact equality: `datetime.now` in place of the port would pass a loose check.
    assert deps.tokens.items[0].expires_at == _NOW + timedelta(hours=48)
    assert deps.tokens.items[0].expires_at.tzinfo is not None


async def test_each_registration_gets_its_own_token() -> None:
    """Two registrations get different tokens."""
    deps = _Deps()
    use_case = deps.use_case()
    _ = await use_case(_command("a1@b.co"))
    _ = await use_case(_command("a2@b.co"))
    await deps.deliver()

    first, second = deps.email.sent[0][1], deps.email.sent[1][1]
    assert first != second
    assert deps.tokens.items[0].token_hash != deps.tokens.items[1].token_hash
    # Length hints at entropy: 32 bytes in base64url are 43 characters.
    assert len(first) >= 43


async def test_duplicate_email_is_rejected() -> None:
    """The store catches a taken address and the use case passes it on."""
    deps = _Deps()
    use_case = deps.use_case()
    _ = await use_case(_command("dup@b.co"))
    with pytest.raises(EmailAlreadyTakenError):
        _ = await use_case(_command("dup@b.co"))


async def test_duplicate_email_leaves_no_second_account() -> None:
    """A taken address creates no account, token or event."""
    deps = _Deps()
    use_case = deps.use_case()
    _ = await use_case(_command("dup2@b.co"))
    await deps.deliver()  # the first registration: one token, one letter
    with pytest.raises(EmailAlreadyTakenError):
        _ = await use_case(_command("dup2@b.co"))

    assert len(deps.users.items) == 1
    assert len(deps.tokens.items) == 1
    assert len(deps.email.sent) == 1
    # Only the unique index catches the duplicate: a pre-check would leave the count at one.
    assert deps.users.add_attempts == 2
    # The duplicate failed on insert, before the outbox write: no event.
    assert deps.outbox.events == []


async def test_duplicate_check_is_case_insensitive() -> None:
    """The case of an address does not open a second account."""
    deps = _Deps()
    use_case = deps.use_case()
    _ = await use_case(_command("Case@b.co"))
    with pytest.raises(EmailAlreadyTakenError):
        _ = await use_case(_command("case@B.CO"))


async def test_short_password_is_rejected() -> None:
    """A short password is refused before anything is stored."""
    deps = _Deps()
    with pytest.raises(WeakPasswordError):
        _ = await deps.use_case()(_command("s@b.co", password="short"))

    assert deps.users.items == {}
    assert deps.uow.committed is False


@pytest.mark.parametrize(
    "password",
    ["no upper case 1", "NO LOWER CASE 1", "Aa" + "ю" * 36],
    ids=["no-upper", "no-lower", "over-72-bytes"],
)
async def test_a_password_against_the_rules_is_rejected(password: str) -> None:
    """A password needs an upper and a lower case letter and fits bcrypt."""
    deps = _Deps()
    with pytest.raises(WeakPasswordError):
        _ = await deps.use_case()(_command("c@b.co", password=password))

    assert deps.users.items == {}


async def test_the_role_and_profile_are_kept() -> None:
    """The picked role and the given profile reach the account."""
    deps = _Deps()
    profile = Profile(first_name_ru="Иван", group_number="Б21-505")

    user_id = await deps.use_case()(
        RegisterCommand(
            email="t@b.co",
            password=_GOOD_PASSWORD,
            role=Role.TEACHER,
            profile=profile,
        ),
    )

    user = deps.users.items[user_id]
    assert user.role is Role.TEACHER
    assert user.profile == profile


async def test_nothing_is_committed_when_the_outbox_write_fails() -> None:
    """A failed event write leaves nothing half-done: no commit."""

    class _ExplodingOutbox(FakeOutbox):
        @override
        async def add(self, events: Sequence[DomainEvent]) -> None:
            del events
            msg = "outbox is down"
            raise RuntimeError(msg)

    deps = _Deps(outbox=_ExplodingOutbox())
    with pytest.raises(RuntimeError):
        _ = await deps.use_case()(_command("x@b.co"))

    assert deps.uow.committed is False
    assert deps.uow.rolled_back is True
    assert deps.email.sent == []


async def test_whitespace_does_not_create_a_second_account() -> None:
    """`` dup@b.co`` and ``dup@b.co`` are one mailbox, so one account."""
    deps = _Deps()
    use_case = deps.use_case()
    _ = await use_case(_command("dup3@b.co"))
    with pytest.raises(EmailAlreadyTakenError):
        _ = await use_case(_command("  dup3@b.co  "))

    assert len(deps.users.items) == 1
