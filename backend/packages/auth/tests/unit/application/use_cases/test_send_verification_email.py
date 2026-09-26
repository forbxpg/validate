"""The handler of `auth.user_registered`."""

from __future__ import annotations

import uuid

import pytest
from auth_fakes import (
    NOW,
    FakeEmailSender,
    FakeTokenRepository,
    FakeUserRepository,
    FrozenClock,
)
from pydantic import SecretStr

from vld.auth.application import (
    SendVerificationEmail,
    UnknownRegisteredUserError,
)
from vld.auth.application.use_cases.shared._token_hashing import hash_token
from vld.auth.config import JwtSettings
from vld.auth.domain import DomainEvent, Role, TokenPurpose, User

# Id of the outbox row the handler derives the token from.
_DELIVERY_ID = 7

_SETTINGS = JwtSettings(secret_key=SecretStr("s" * 32))


def _event(user_id: uuid.UUID) -> DomainEvent:
    return DomainEvent(
        "auth.user_registered",
        {"user_id": str(user_id), "role": str(Role.STUDENT)},
    )


async def test_issues_fresh_token_and_sends_to_stored_address() -> None:
    """The handler issues a token and mails the stored address."""
    users = FakeUserRepository()
    tokens = FakeTokenRepository()
    email = FakeEmailSender()
    user = User.register(
        email="new@b.co",
        password_hash="hashed:pw",
        role=Role.STUDENT,
    )
    await users.add(user)

    handler = SendVerificationEmail(users, tokens, email, FrozenClock(NOW), _SETTINGS)
    recipient, raw = await handler.prepare(_event(user.id), _DELIVERY_ID)
    await handler.deliver(recipient, raw)

    # Exactly one confirmation token for the owner.
    assert len(tokens.items) == 1
    stored = tokens.items[0]
    assert stored.purpose is TokenPurpose.EMAIL_VERIFY
    assert stored.user_id == user.id

    # The letter went to the stored address with the raw token; the database keeps the hash.
    assert len(email.sent) == 1
    sent_to, raw_token = email.sent[0]
    assert sent_to == user.email
    assert hash_token(raw_token) == stored.token_hash


async def test_missing_user_raises_instead_of_sending() -> None:
    """An event about a missing account is a signal, not a quiet success."""
    handler = SendVerificationEmail(
        FakeUserRepository(),
        FakeTokenRepository(),
        FakeEmailSender(),
        FrozenClock(NOW),
        _SETTINGS,
    )
    with pytest.raises(UnknownRegisteredUserError):
        _ = await handler.prepare(_event(uuid.uuid4()), _DELIVERY_ID)
