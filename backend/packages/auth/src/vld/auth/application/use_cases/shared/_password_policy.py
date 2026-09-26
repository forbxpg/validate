"""Password rules shared by every use case that takes a plain password."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import AuthDomainError

if TYPE_CHECKING:
    from vld.auth.config import PasswordSettings

# bcrypt reads only the first 72 bytes: a longer tail would protect nothing.
MAX_PASSWORD_BYTES = 72


class WeakPasswordError(AuthDomainError):
    """The password does not meet the rules."""


def check_password(password: str, settings: PasswordSettings) -> None:
    """Check a password against the rules.

    Args:
        password: str - Plain password.
        settings: PasswordSettings - The rules.

    Raises:
        WeakPasswordError: If the password is too short, too long for bcrypt or
            lacks upper- or lower-case letters.

    """
    if len(password) < settings.min_length:
        msg = f"password must be at least {settings.min_length} characters"
        raise WeakPasswordError(msg)
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        msg = f"password must be at most {MAX_PASSWORD_BYTES} bytes"
        raise WeakPasswordError(msg)
    if sum(char.isupper() for char in password) < settings.min_uppercase:
        msg = f"password needs at least {settings.min_uppercase} upper-case letters"
        raise WeakPasswordError(msg)
    if sum(char.islower() for char in password) < settings.min_lowercase:
        msg = f"password needs at least {settings.min_lowercase} lower-case letters"
        raise WeakPasswordError(msg)
