"""Registering an account."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import check_password
from vld.auth.domain import Profile, User

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import Outbox, PasswordHasher, UserRepository
    from vld.auth.config import PasswordSettings
    from vld.auth.domain import Role
    from vld.core.database import UnitOfWork


def _default_profile() -> Profile:
    return Profile()


@dataclass(frozen=True, slots=True)
class RegisterCommand:
    """A registration request.

    Attributes:
        email: str - Address.
        password: str - Plain password.
        role: Role - Role the user picked.
        profile: Profile - Details given at registration.

    """

    email: str
    password: str
    role: Role
    profile: Profile = field(default_factory=_default_profile)


class RegisterUser:
    """Create an account and record its confirmation letter in the outbox."""

    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        outbox: Outbox,
        uow: UnitOfWork,
        settings: PasswordSettings,
    ) -> None:
        self._users: UserRepository = users
        self._hasher: PasswordHasher = hasher
        self._outbox: Outbox = outbox
        self._uow: UnitOfWork = uow
        self._settings: PasswordSettings = settings

    async def __call__(self, command: RegisterCommand) -> uuid.UUID:
        """Register a user.

        Args:
            command: RegisterCommand - Registration data.

        Returns:
            uuid.UUID - Id of the new account.

        """
        check_password(command.password, self._settings)
        # Before the transaction: hashing is slow and must not hold a connection.
        password_hash = await self._hasher.hash(command.password)

        async with self._uow:
            user = User.register(
                email=command.email,
                password_hash=password_hash,
                role=command.role,
                profile=command.profile,
            )
            # The insert goes first: a taken address aborts the transaction here.
            await self._users.add(user)
            await self._outbox.add(user.pull_events())
            await self._uow.commit()
        return user.id
