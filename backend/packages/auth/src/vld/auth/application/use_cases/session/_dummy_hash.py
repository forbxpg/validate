"""Equal timing of a login with an unknown address."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vld.auth.application.ports import PasswordHasher

_DUMMY_PASSWORD_BYTES = 32


class DummyHash:
    """A hash no password matches, checked when the address is unknown.

    Without it a login with an unknown address would answer faster than one
    with a wrong password, and the timing would reveal which addresses exist.
    """

    _value: ClassVar[str | None] = None

    @classmethod
    async def get(cls, hasher: PasswordHasher) -> str:
        """Return the hash, computing it on first use.

        Args:
            hasher: PasswordHasher - Hasher whose parameters to use.

        Returns:
            str - A hash no password matches.

        """
        if cls._value is None:
            cls._value = await hasher.hash(secrets.token_urlsafe(_DUMMY_PASSWORD_BYTES))
        return cls._value


async def warm_password_verification(hasher: PasswordHasher) -> None:
    """Compute the dummy hash at startup, before the first login needs it.

    Args:
        hasher: PasswordHasher - Hasher whose parameters to use.

    """
    _ = await DummyHash.get(hasher)
