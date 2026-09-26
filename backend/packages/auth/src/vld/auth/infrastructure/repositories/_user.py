"""Store of accounts over SQLAlchemy."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from vld.auth.application.ports import UsersPage
from vld.auth.domain import EmailAlreadyTakenError, EntityNotFoundError, normalize_email
from vld.auth.infrastructure.mappers import (
    apply_user_to_model,
    user_from_model,
    user_to_model,
)
from vld.auth.infrastructure.models import EMAIL_UNIQUE_CONSTRAINT, UserModel
from vld.core.database import is_unique_violation

if TYPE_CHECKING:
    import uuid

    from sqlalchemy import ColumnElement, CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession

    from vld.auth.domain import Role, User


class SqlAlchemyUserRepository:
    """Store of accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, user: User) -> None:
        """Store a new account, flushing the row at once.

        Args:
            user: User - The account.

        Raises:
            EmailAlreadyTakenError: If the address is taken.
            IntegrityError: If another constraint is violated.

        """
        self._session.add(user_to_model(user))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if is_unique_violation(exc, EMAIL_UNIQUE_CONSTRAINT):
                msg = "email already taken"
                raise EmailAlreadyTakenError(msg) from exc
            raise

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Find an account by id.

        Args:
            user_id: uuid.UUID - The id.

        Returns:
            User | None - The account, or None.

        """
        model = await self._session.get(UserModel, user_id)
        return None if model is None else user_from_model(model)

    async def get_by_email(self, email: str) -> User | None:
        """Find an account by address.

        Args:
            email: str - The address as typed.

        Returns:
            User | None - The account, or None.

        """
        model = await self._session.scalar(
            select(UserModel).where(UserModel.email == normalize_email(email)),
        )
        return None if model is None else user_from_model(model)

    async def search(
        self,
        *,
        role: Role | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> UsersPage:
        """Select a page of accounts by filters.

        Args:
            role: Role | None - Role, or None for any.
            is_active: bool | None - Access state, or None for any.
            limit: int - Page size.
            offset: int - Accounts to skip.

        Returns:
            UsersPage - The page and the number of matching accounts.

        """
        conditions: list[ColumnElement[bool]] = []
        if role is not None:
            conditions.append(UserModel.role == role)
        if is_active is not None:
            conditions.append(UserModel.is_active.is_(is_active))
        total = await self._session.scalar(
            select(func.count()).select_from(UserModel).where(*conditions),
        )
        models = await self._session.scalars(
            select(UserModel)
            .where(*conditions)
            .order_by(UserModel.created_at, UserModel.id)
            .limit(limit)
            .offset(offset),
        )
        return UsersPage(
            users=[user_from_model(model) for model in models],
            total=int(total or 0),
        )

    async def update_password_hash(
        self,
        user_id: uuid.UUID,
        expected_hash: str,
        new_hash: str,
    ) -> bool:
        """Replace the password hash with a conditional UPDATE.

        Args:
            user_id: uuid.UUID - Owner.
            expected_hash: str - Hash the use case has just checked.
            new_hash: str - New hash.

        Returns:
            bool - True if the row was updated.

        """
        # DML returns a CursorResult, which has `rowcount`.
        result = cast(
            "CursorResult[object]",
            await self._session.execute(
                update(UserModel)
                .where(
                    UserModel.id == user_id,
                    UserModel.password_hash == expected_hash,
                )
                .values(password_hash=new_hash)
                .execution_options(synchronize_session="fetch"),
            ),
        )
        return bool(result.rowcount)

    async def update(self, user: User) -> None:
        """Copy the changes of an account into its stored row.

        Args:
            user: User - The account.

        Raises:
            EntityNotFoundError: If the row is not stored.

        """
        model = await self._session.get(UserModel, user.id)
        if model is None:
            msg = f"user {user.id} is not stored"
            raise EntityNotFoundError(msg)
        apply_user_to_model(user, model)

    async def delete(self, user_id: uuid.UUID) -> bool:
        """Delete an account; its tokens go with it by the foreign key.

        Args:
            user_id: uuid.UUID - The account.

        Returns:
            bool - True if a row was deleted.

        """
        result = cast(
            "CursorResult[object]",
            await self._session.execute(
                delete(UserModel).where(UserModel.id == user_id),
            ),
        )
        return bool(result.rowcount)
