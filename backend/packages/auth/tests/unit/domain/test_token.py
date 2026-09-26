"""The one-time verification token."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from vld.auth.domain import (
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenIdAlreadyAssignedError,
    TokenPurpose,
    VerificationToken,
)

_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _issued() -> VerificationToken:
    """Issue a token for the tests."""
    return VerificationToken.issue(
        user_id=uuid.uuid4(),
        token_hash="hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        now=_NOW,
        ttl=timedelta(hours=48),
    )


def test_issue_sets_expiry() -> None:
    """Issuing sets the expiry from the lifetime."""
    token = _issued()
    assert token.expires_at == _NOW + timedelta(hours=48)
    assert token.used_at is None


def test_consume_marks_used() -> None:
    """Consuming records the moment of use."""
    token = _issued()
    token.consume(now=_NOW + timedelta(hours=1))
    assert token.used_at == _NOW + timedelta(hours=1)


def test_expired_token_is_rejected() -> None:
    """An expired token is refused."""
    token = _issued()
    with pytest.raises(TokenExpiredError):
        token.consume(now=_NOW + timedelta(hours=49))


def test_token_cannot_be_used_twice() -> None:
    """A token works once."""
    token = _issued()
    token.consume(now=_NOW)
    with pytest.raises(TokenAlreadyUsedError):
        token.consume(now=_NOW)


def test_expires_at_is_required() -> None:
    """The constructor refuses a token without an expiry."""
    # The annotation is not the only guard: the constructor checks at run time.
    with pytest.raises(TokenExpiredError):
        _ = VerificationToken(
            id=None,
            user_id=uuid.uuid4(),
            token_hash="hash",
            purpose=TokenPurpose.EMAIL_VERIFY,
            expires_at=None,  # pyright: ignore[reportArgumentType]
            used_at=None,
        )


def test_id_is_none_before_persistence() -> None:
    """A token has no id until it is stored."""
    token = _issued()
    assert token.id is None


def test_id_can_be_assigned_once_after_persistence() -> None:
    """The mapper assigns the id once, after the flush."""
    # Only the infrastructure mapper may set this field, once, after the flush.
    token = _issued()
    token.id = 1
    assert token.id == 1


def test_id_cannot_be_reassigned() -> None:
    """A second id would split the token from its row."""
    # A second assignment would split the aggregate from its row.
    token = _issued()
    token.id = 1
    with pytest.raises(TokenIdAlreadyAssignedError):
        token.id = 2
