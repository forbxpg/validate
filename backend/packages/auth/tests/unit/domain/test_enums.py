"""Values of the enums, which the database types repeat."""

from __future__ import annotations

from vld.auth.domain import Role, TokenPurpose


def test_roles_match_the_database_enum() -> None:
    """Roles spell the labels of the database enum."""
    # The migration spells these labels out; alembic check does not compare them.
    assert [role.value for role in Role] == ["student", "teacher"]


def test_token_purposes_match_the_database_enum() -> None:
    """Token purposes spell the labels of the database enum."""
    assert [purpose.value for purpose in TokenPurpose] == [
        "email_verify",
        "password_reset",
    ]
