"""Confirming an address."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.application.use_cases.shared import InvalidTokenError, hash_token
from vld.auth.domain import TokenAlreadyUsedError, TokenPurpose

if TYPE_CHECKING:
    from vld.auth.application.ports import Clock, TokenRepository, UserRepository
    from vld.core.database import UnitOfWork


class VerifyEmail:
    """Use up a confirmation token and confirm the address."""

    def __init__(
        self,
        users: UserRepository,
        tokens: TokenRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users: UserRepository = users
        self._tokens: TokenRepository = tokens
        self._clock: Clock = clock
        self._uow: UnitOfWork = uow

    async def __call__(self, raw_token: str) -> None:
        """Confirm an address with the token from the letter.

        Args:
            raw_token: str - Token from the link.

        Raises:
            InvalidTokenError: If the token is unknown or has another purpose.
            TokenAlreadyUsedError: If the token was used but the address is still
                unconfirmed.

        """
        async with self._uow:
            token = await self._tokens.get_by_hash(
                hash_token(raw_token),
                TokenPurpose.EMAIL_VERIFY,
            )
            if token is None:
                msg = "verification token not found"
                raise InvalidTokenError(msg)
            user = await self._users.get_by_id(token.user_id)
            if user is None:
                msg = "token owner not found"
                raise InvalidTokenError(msg)
            now = self._clock.now()
            try:
                # The conditional UPDATE of the repository keeps this atomic.
                token.consume(now=now)
                await self._tokens.update(token)
            except TokenAlreadyUsedError:
                # A second click on a working link is not an error.
                if user.email_verified:
                    return
                raise
            user.verify_email(now)
            await self._users.update(user)
            await self._uow.commit()
