"""The User aggregate: credentials, role, access state and profile."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

from ._email import normalize_email
from ._errors import AccountDeactivatedError, EmailNotVerifiedError
from ._events import USER_REGISTERED_EVENT, DomainEvent
from ._profile import Profile

if TYPE_CHECKING:
    from datetime import datetime

    from ._enums import Role


class User:  # ruff: ignore[too-many-public-methods] -- the aggregate is the one place its rules live
    """An account of the service."""

    __slots__: tuple[str, ...] = (
        "_email",
        "_email_verified_at",
        "_events",
        "_id",
        "_is_active",
        "_is_admin",
        "_password_hash",
        "_profile",
        "_role",
        "_tokens_invalidated_after",
    )

    def __init__(  # ruff: ignore[too-many-arguments] -- the aggregate takes its whole state
        self,
        *,
        id: uuid.UUID,  # ruff: ignore[builtin-argument-shadowing]
        email: str,
        email_verified_at: datetime | None,
        password_hash: str,
        role: Role,
        is_admin: bool,
        is_active: bool,
        tokens_invalidated_after: datetime | None = None,
        profile: Profile | None = None,
    ) -> None:
        self._id: uuid.UUID = id
        self._email: str = normalize_email(email)
        self._email_verified_at: datetime | None = email_verified_at
        self._password_hash: str = password_hash
        self._role: Role = role
        self._is_admin: bool = is_admin
        self._is_active: bool = is_active
        self._tokens_invalidated_after: datetime | None = tokens_invalidated_after
        self._profile: Profile = profile or Profile()
        self._events: list[DomainEvent] = []

    @classmethod
    def register(
        cls,
        email: str,
        password_hash: str,
        role: Role,
        profile: Profile | None = None,
    ) -> User:
        """Create an account and record the letter it needs.

        Args:
            email: str - Address.
            password_hash: str - Hash of the chosen password.
            role: Role - Role picked at registration.
            profile: Profile | None - Details given at registration.

        Returns:
            User - Active account with an unconfirmed address.

        """
        user = cls(
            id=uuid.uuid4(),
            email=email,
            email_verified_at=None,
            password_hash=password_hash,
            role=role,
            is_admin=False,
            is_active=True,
            profile=profile,
        )
        user._events.append(
            DomainEvent(USER_REGISTERED_EVENT, {"user_id": str(user.id)}),
        )
        return user

    @property
    def id(self) -> uuid.UUID:
        """Account id.

        Returns:
            uuid.UUID - The id.

        """
        return self._id

    @property
    def email(self) -> str:
        """Normalized address.

        Returns:
            str - The address.

        """
        return self._email

    @property
    def email_verified_at(self) -> datetime | None:
        """When the address was confirmed.

        Returns:
            datetime | None - The moment, or None while unconfirmed.

        """
        return self._email_verified_at

    @property
    def email_verified(self) -> bool:
        """Say whether the address is confirmed.

        Returns:
            bool - True once confirmed.

        """
        return self._email_verified_at is not None

    @property
    def password_hash(self) -> str:
        """Hash of the password.

        Returns:
            str - The hash.

        """
        return self._password_hash

    @property
    def role(self) -> Role:
        """Role picked at registration or set by an admin.

        Returns:
            Role - The role.

        """
        return self._role

    @property
    def is_admin(self) -> bool:
        """Admin rights, granted only from the console.

        Returns:
            bool - True for an admin.

        """
        return self._is_admin

    @property
    def is_active(self) -> bool:
        """Whether the account may log in at all.

        Returns:
            bool - False once an admin turned it off.

        """
        return self._is_active

    @property
    def tokens_invalidated_after(self) -> datetime | None:
        """Moment before which every token of the account is void.

        Returns:
            datetime | None - The moment, or None if never set.

        """
        return self._tokens_invalidated_after

    @property
    def profile(self) -> Profile:
        """Personal details.

        Returns:
            Profile - The details.

        """
        return self._profile

    def pull_events(self) -> list[DomainEvent]:
        """Take the events recorded since the last call.

        Returns:
            list[DomainEvent] - Events for the outbox, in order.

        """
        events, self._events = self._events, []
        return events

    def ensure_can_authenticate(self, *, require_verified_email: bool) -> None:
        """Refuse an account that may not log in now.

        Args:
            require_verified_email: bool - Whether an unconfirmed address blocks it.

        Raises:
            AccountDeactivatedError: If an admin turned the account off.
            EmailNotVerifiedError: If the address must be and is not confirmed.

        """
        if not self._is_active:
            msg = f"account {self._id} is deactivated"
            raise AccountDeactivatedError(msg)
        if require_verified_email and not self.email_verified:
            msg = "email is not verified"
            raise EmailNotVerifiedError(msg)

    def verify_email(self, now: datetime) -> None:
        """Mark the address confirmed, keeping the first confirmation.

        Args:
            now: datetime - Moment of the confirmation.

        """
        if self._email_verified_at is None:
            self._email_verified_at = now

    def invalidate_tokens(self, now: datetime) -> None:
        """Void every token issued up to this moment.

        Tokens carry `iat` in whole seconds, so the mark is rounded up: a token
        issued in the same second is voided too.

        Args:
            now: datetime - Current moment.

        """
        mark = now + timedelta(microseconds=-now.microsecond % 1_000_000)
        current = self._tokens_invalidated_after
        if current is None or mark > current:
            self._tokens_invalidated_after = mark

    def set_password(self, password_hash: str, *, now: datetime) -> None:
        """Change the password and end every session with it.

        Args:
            password_hash: str - Hash of the new password.
            now: datetime - Moment of the change.

        """
        self._password_hash = password_hash
        self.invalidate_tokens(now)

    def reset_password(self, password_hash: str, *, now: datetime) -> None:
        """Set a password through a link from a letter.

        Following the link proves the address belongs to the user, so it also
        confirms the address. An account taken on someone else's address thus
        passes to its owner, and the other person's sessions end.

        Args:
            password_hash: str - Hash of the new password.
            now: datetime - Moment of the reset.

        """
        self.set_password(password_hash, now=now)
        self.verify_email(now)

    def deactivate(self, now: datetime) -> None:
        """Turn the account off and end its sessions.

        Args:
            now: datetime - Moment of the change.

        """
        self._is_active = False
        self.invalidate_tokens(now)

    def activate(self) -> None:
        """Turn the account back on."""
        self._is_active = True

    def change_role(self, role: Role) -> None:
        """Set another role.

        Args:
            role: Role - New role.

        """
        self._role = role

    def grant_admin(self) -> None:
        """Give admin rights."""
        self._is_admin = True

    def update_profile(self, profile: Profile) -> None:
        """Replace the personal details.

        Args:
            profile: Profile - New details.

        """
        self._profile = profile
