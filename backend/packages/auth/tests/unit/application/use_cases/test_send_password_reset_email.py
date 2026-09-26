"""The handler of `auth.password_reset_requested`."""

from __future__ import annotations

import uuid
from datetime import timedelta

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
    SendPasswordResetEmail,
    UnknownResetTargetError,
)
from vld.auth.application.use_cases.shared._email_verification import (
    derive_verification_token,
    issue_verification,
)
from vld.auth.application.use_cases.shared._password_reset import (
    derive_password_reset_token,
    issue_password_reset,
)
from vld.auth.application.use_cases.shared._token_hashing import hash_token
from vld.auth.config import JwtSettings
from vld.auth.domain import DomainEvent, Role, TokenPurpose, User

# Id of the outbox row the handler derives the token from.
_DELIVERY_ID = 7

_SECRET = "s" * 32
_SETTINGS = JwtSettings(secret_key=SecretStr(_SECRET))


def _event(user_id: uuid.UUID) -> DomainEvent:
    """Build the event exactly as the use case writes it."""
    return DomainEvent(
        "auth.password_reset_requested",
        {"user_id": str(user_id)},
    )


def _handler(
    users: FakeUserRepository,
    tokens: FakeTokenRepository,
    email: FakeEmailSender,
) -> SendPasswordResetEmail:
    return SendPasswordResetEmail(users, tokens, email, FrozenClock(NOW), _SETTINGS)


async def _seed(users: FakeUserRepository) -> User:
    user = User.register(
        email="lost@b.co",
        password_hash="hashed:pw",
        role=Role.STUDENT,
    )
    await users.add(user)
    return user


async def test_issues_a_reset_token_and_mails_the_stored_address() -> None:
    """The handler issues a reset token and mails the stored address."""
    users, tokens, email = (
        FakeUserRepository(),
        FakeTokenRepository(),
        FakeEmailSender(),
    )
    user = await _seed(users)

    handler = _handler(users, tokens, email)
    recipient, raw = await handler.prepare(_event(user.id), _DELIVERY_ID)
    await handler.deliver(recipient, raw)

    assert len(tokens.items) == 1
    stored = tokens.items[0]
    assert stored.purpose is TokenPurpose.PASSWORD_RESET
    assert stored.user_id == user.id

    assert email.sent == [], "no confirmation letter here"
    assert len(email.reset_sent) == 1
    sent_to, raw_token = email.reset_sent[0]
    assert sent_to == user.email
    assert hash_token(raw_token) == stored.token_hash


async def test_a_repeated_row_reuses_the_same_token() -> None:
    """A retried outbox row keeps a single live reset token."""
    users, tokens, email = (
        FakeUserRepository(),
        FakeTokenRepository(),
        FakeEmailSender(),
    )
    user = await _seed(users)
    handler = _handler(users, tokens, email)

    _, first = await handler.prepare(_event(user.id), _DELIVERY_ID)
    _, second = await handler.prepare(_event(user.id), _DELIVERY_ID)

    assert len(tokens.items) == 1
    assert first == second, "the link must be the same"


async def test_a_reset_token_differs_from_a_verification_token() -> None:
    """The two purposes derive different tokens from one delivery id."""
    reset = derive_password_reset_token(_SECRET, _DELIVERY_ID)
    verification = derive_verification_token(_SECRET, _DELIVERY_ID)

    assert reset != verification


async def test_a_missing_user_raises_instead_of_sending() -> None:
    """An event about a missing account is a signal, not a quiet success."""
    email = FakeEmailSender()
    handler = _handler(FakeUserRepository(), FakeTokenRepository(), email)

    with pytest.raises(UnknownResetTargetError):
        _ = await handler.prepare(_event(uuid.uuid4()), _DELIVERY_ID)

    assert email.reset_sent == []


async def test_a_reset_link_dies_within_the_hour() -> None:
    """A reset link lives an hour, much shorter than a confirmation link."""
    user_id = uuid.uuid4()
    _, reset = issue_password_reset(user_id, NOW)
    _, verification = issue_verification(user_id, NOW)

    assert reset.expires_at - NOW == timedelta(hours=1)
    assert reset.expires_at < verification.expires_at
