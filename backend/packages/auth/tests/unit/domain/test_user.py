"""The User aggregate: registration, access, tokens, password, admin changes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from vld.auth.domain import (
    USER_REGISTERED_EVENT,
    AccountDeactivatedError,
    EmailNotVerifiedError,
    Profile,
    Role,
    User,
)

NOW = datetime(2026, 9, 26, 12, 0, 0, 250_000, tzinfo=UTC)


def _user(*, verified: bool = True, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="student@mephi.ru",
        email_verified_at=NOW if verified else None,
        password_hash="hash",
        role=Role.STUDENT,
        is_admin=False,
        is_active=active,
    )


def test_register_normalizes_the_email_and_records_the_letter() -> None:
    """Registration normalizes the address and records the letter."""
    user = User.register("  Student@MEPhI.ru ", "hash", Role.TEACHER)

    assert user.email == "student@mephi.ru"
    assert user.role is Role.TEACHER
    assert user.is_active
    assert not user.is_admin
    assert not user.email_verified
    assert user.profile == Profile()
    [event] = user.pull_events()
    assert event.name == USER_REGISTERED_EVENT
    assert event.payload == {"user_id": str(user.id)}


def test_pull_events_drains_them() -> None:
    """Pulled events are gone."""
    user = User.register("a@b.co", "hash", Role.STUDENT)
    _ = user.pull_events()

    assert user.pull_events() == []


def test_register_keeps_the_profile() -> None:
    """Registration keeps the given profile."""
    profile = Profile(first_name_ru="Иван", group_number="Б21-505")

    user = User.register("a@b.co", "hash", Role.STUDENT, profile)

    assert user.profile == profile


def test_a_deactivated_account_cannot_authenticate() -> None:
    """A deactivated account cannot log in."""
    with pytest.raises(AccountDeactivatedError):
        _user(active=False).ensure_can_authenticate(require_verified_email=False)


def test_an_unverified_address_blocks_only_when_required() -> None:
    """An unconfirmed address blocks only when the setting says so."""
    user = _user(verified=False)

    user.ensure_can_authenticate(require_verified_email=False)
    with pytest.raises(EmailNotVerifiedError):
        user.ensure_can_authenticate(require_verified_email=True)


def test_deactivation_is_checked_before_verification() -> None:
    """A deactivated account hears about deactivation first."""
    with pytest.raises(AccountDeactivatedError):
        _user(verified=False, active=False).ensure_can_authenticate(
            require_verified_email=True,
        )


def test_verify_email_keeps_the_first_confirmation() -> None:
    """A second confirmation keeps the first moment."""
    user = _user(verified=False)

    user.verify_email(NOW)
    user.verify_email(NOW + timedelta(days=1))

    assert user.email_verified_at == NOW


def test_invalidate_tokens_rounds_up_to_the_next_whole_second() -> None:
    """The mark rounds up, voiding tokens of the same second."""
    user = _user()

    user.invalidate_tokens(NOW)

    # A token issued in the same second carries iat 12:00:00 and must be void.
    assert user.tokens_invalidated_after == NOW.replace(second=1, microsecond=0)


def test_invalidate_tokens_on_a_whole_second_keeps_it() -> None:
    """A mark on a whole second stays as it is."""
    user = _user()
    whole = NOW.replace(microsecond=0)

    user.invalidate_tokens(whole)

    assert user.tokens_invalidated_after == whole


def test_invalidate_tokens_never_moves_back() -> None:
    """The mark never moves back."""
    user = _user()
    user.invalidate_tokens(NOW)

    user.invalidate_tokens(NOW - timedelta(hours=1))

    assert user.tokens_invalidated_after == NOW.replace(second=1, microsecond=0)


def test_set_password_ends_every_session() -> None:
    """A new password ends every session."""
    user = _user()

    user.set_password("new-hash", now=NOW)

    assert user.password_hash == "new-hash"
    assert user.tokens_invalidated_after is not None


def test_reset_password_also_confirms_the_address() -> None:
    """A reset through a letter confirms the address."""
    user = _user(verified=False)

    user.reset_password("new-hash", now=NOW)

    assert user.password_hash == "new-hash"
    assert user.email_verified_at == NOW
    assert user.tokens_invalidated_after is not None


def test_deactivate_ends_every_session_and_activate_restores_access() -> None:
    """Deactivation ends the sessions; activation restores access."""
    user = _user()

    user.deactivate(NOW)

    assert not user.is_active
    assert user.tokens_invalidated_after is not None
    user.activate()
    assert user.is_active


def test_admin_changes() -> None:
    """Role, admin rights and profile change as asked."""
    user = _user()

    user.change_role(Role.TEACHER)
    user.grant_admin()
    user.update_profile(Profile(last_name_en="Ivanov"))

    assert user.role is Role.TEACHER
    assert user.is_admin
    assert user.profile == Profile(last_name_en="Ivanov")
