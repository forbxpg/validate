"""One-time token of a confirmation or reset link."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._errors import AuthDomainError

if TYPE_CHECKING:
    import uuid
    from datetime import datetime, timedelta

    from ._enums import TokenPurpose


class TokenExpiredError(AuthDomainError):
    """The token expired, or had no expiry at all."""


class TokenAlreadyUsedError(AuthDomainError):
    """The token was already used."""


class TokenIdAlreadyAssignedError(AuthDomainError):
    """The token id is already assigned and may not change."""


class VerificationToken:
    """A one-time token that always expires."""

    __slots__: tuple[str, ...] = (
        "_expires_at",
        "_id",
        "_purpose",
        "_token_hash",
        "_used_at",
        "_user_id",
    )

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        *,
        id: int | None,  # ruff: ignore[builtin-argument-shadowing]
        user_id: uuid.UUID,
        token_hash: str,
        purpose: TokenPurpose,
        expires_at: datetime,
        used_at: datetime | None,
    ) -> None:
        self._validate_expires_at(expires_at)
        self._id: int | None = id
        self._user_id: uuid.UUID = user_id
        self._token_hash: str = token_hash
        self._purpose: TokenPurpose = purpose
        self._used_at: datetime | None = used_at
        self._expires_at: datetime = expires_at

    @property
    def id(self) -> int | None:
        """Token id.

        Returns:
            int | None - The id, or None until stored.

        """
        return self._id

    @classmethod
    def _validate_expires_at(cls, expires_at: datetime | None) -> None:
        """Refuse a token without an expiry.

        Args:
            expires_at: datetime | None - Expiry to check.

        Raises:
            TokenExpiredError: If there is no expiry.

        """
        if expires_at is None:
            msg = "expires_at is required"
            raise TokenExpiredError(msg)

    @id.setter  # ruff: ignore[builtin-attribute-shadowing]
    def id(self, value: int) -> None:
        """Assign the id the database generated on insert.

        Raises:
            TokenIdAlreadyAssignedError: If an id is already assigned.

        """
        if self._id is not None:
            msg = "id is already assigned"
            raise TokenIdAlreadyAssignedError(msg)
        self._id = value

    @property
    def user_id(self) -> uuid.UUID:
        """Owner of the token.

        Returns:
            uuid.UUID - The owner.

        """
        return self._user_id

    @property
    def token_hash(self) -> str:
        """Hash of the issued value.

        Returns:
            str - The hash.

        """
        return self._token_hash

    @property
    def purpose(self) -> TokenPurpose:
        """What the token is for.

        Returns:
            TokenPurpose - The purpose.

        """
        return self._purpose

    @property
    def expires_at(self) -> datetime:
        """When the token expires.

        Returns:
            datetime - The expiry.

        """
        return self._expires_at

    @property
    def used_at(self) -> datetime | None:
        """When the token was used.

        Returns:
            datetime | None - The moment, or None while unused.

        """
        return self._used_at

    @classmethod
    def issue(
        cls,
        user_id: uuid.UUID,
        token_hash: str,
        purpose: TokenPurpose,
        now: datetime,
        ttl: timedelta,
    ) -> VerificationToken:
        """Issue a token.

        Args:
            user_id: uuid.UUID - Owner.
            token_hash: str - Hash of the value sent to the user.
            purpose: TokenPurpose - What the token is for.
            now: datetime - Current moment, passed in so expiry is testable.
            ttl: timedelta - Lifetime.

        Returns:
            VerificationToken - An unused token.

        """
        return cls(
            id=None,
            user_id=user_id,
            token_hash=token_hash,
            purpose=purpose,
            expires_at=now + ttl,
            used_at=None,
        )

    def consume(self, now: datetime) -> None:
        """Use the token up.

        Args:
            now: datetime - Current moment.

        Raises:
            TokenAlreadyUsedError: If the token was already used.
            TokenExpiredError: If the token expired.

        """
        if self._used_at is not None:
            msg = "token already used"
            raise TokenAlreadyUsedError(msg)
        if now > self._expires_at:
            msg = "token expired"
            raise TokenExpiredError(msg)
        self._used_at = now
