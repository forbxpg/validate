"""Store of one-time tokens over SQLAlchemy."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import select, update

from vld.auth.domain import EntityNotFoundError, TokenAlreadyUsedError
from vld.auth.infrastructure.mappers import token_from_model, token_to_model
from vld.auth.infrastructure.models import VerificationTokenModel

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from sqlalchemy import CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession

    from vld.auth.domain import TokenPurpose, VerificationToken


class SqlAlchemyTokenRepository:
    """Store of one-time tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, token: VerificationToken) -> None:
        """Store an issued token and give the entity the id the database chose.

        Args:
            token: VerificationToken - The token.

        """
        model = token_to_model(token)
        self._session.add(model)
        await self._session.flush()
        token.id = model.id

    async def get_by_hash(
        self,
        token_hash: str,
        purpose: TokenPurpose,
    ) -> VerificationToken | None:
        """Find a token by the hash of its value and its purpose.

        Args:
            token_hash: str - Hash of the value.
            purpose: TokenPurpose - Purpose the token is looked up for.

        Returns:
            VerificationToken | None - The token, or None.

        """
        result = await self._session.execute(
            select(VerificationTokenModel).where(
                VerificationTokenModel.token_hash == token_hash,
                VerificationTokenModel.purpose == purpose,
            ),
        )
        model = result.scalar_one_or_none()
        return None if model is None else token_from_model(model)

    async def consume_outstanding(
        self,
        user_id: uuid.UUID,
        purpose: TokenPurpose,
        *,
        now: datetime,
    ) -> None:
        """Use up every unused token of an account with this purpose in one UPDATE.

        Args:
            user_id: uuid.UUID - Owner of the tokens.
            purpose: TokenPurpose - Purpose whose tokens are used up.
            now: datetime - Moment of use.

        """
        _ = await self._session.execute(
            update(VerificationTokenModel)
            .where(
                VerificationTokenModel.user_id == user_id,
                VerificationTokenModel.purpose == purpose,
                VerificationTokenModel.used_at.is_(None),
            )
            .values(used_at=now)
            .execution_options(synchronize_session="fetch"),
        )

    async def update(self, token: VerificationToken) -> None:
        """Mark the token row used with a conditional UPDATE.

        Args:
            token: VerificationToken - The token.

        Raises:
            TokenAlreadyUsedError: If another request used the row first.
            EntityNotFoundError: If the token was never stored or its row is gone.

        """
        if token.id is None:
            # update() before add(): same outcome as a race, told apart by the message.
            msg = "token was never stored: id is not assigned"
            raise EntityNotFoundError(msg)

        # DML returns a CursorResult, which has `rowcount`.
        result = cast(
            "CursorResult[object]",
            await self._session.execute(
                update(VerificationTokenModel)
                .where(
                    VerificationTokenModel.id == token.id,
                    VerificationTokenModel.used_at.is_(None),
                )
                .values(used_at=token.used_at)
                .execution_options(synchronize_session="fetch"),
            ),
        )
        if result.rowcount:
            return

        # No row updated: the row is gone or already used; one query tells which.
        stored = await self._session.get(VerificationTokenModel, token.id)
        if stored is None:
            msg = f"token {token.id} is not stored"
            raise EntityNotFoundError(msg)
        msg = f"token {token.id} was already consumed"
        raise TokenAlreadyUsedError(msg)
