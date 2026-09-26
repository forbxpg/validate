"""Registration against a live PostgreSQL: the race on the unique index."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest
from auth_fakes import GOOD_PASSWORD, PASSWORD_SETTINGS, FakeHasher
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vld.auth.application import RegisterCommand, RegisterUser
from vld.auth.domain import EmailAlreadyTakenError, Role
from vld.auth.infrastructure import SqlAlchemyOutbox, SqlAlchemyUserRepository
from vld.auth.infrastructure.models import UserModel
from vld.core.database import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


async def _register(engine: AsyncEngine, email: str) -> uuid.UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        use_case = RegisterUser(
            users=SqlAlchemyUserRepository(session),
            hasher=FakeHasher(),
            outbox=SqlAlchemyOutbox(session),
            uow=SqlAlchemyUnitOfWork(session),
            settings=PASSWORD_SETTINGS,
        )
        return await use_case(
            RegisterCommand(email=email, password=GOOD_PASSWORD, role=Role.STUDENT),
        )


@pytest.mark.integration
async def test_concurrent_registration_loses_with_a_domain_error(
    db_engine: AsyncEngine,
) -> None:
    """Of two concurrent registrations one wins, the other gets a domain error."""
    email = f"race-{uuid.uuid4().hex}@b.co"

    results = await asyncio.gather(
        _register(db_engine, email),
        _register(db_engine, email.upper()),
        return_exceptions=True,
    )

    created = [r for r in results if isinstance(r, uuid.UUID)]
    failures = [r for r in results if isinstance(r, BaseException)]
    assert len(created) == 1, f"expected exactly one account, got {results}"
    assert len(failures) == 1, f"expected exactly one refusal, got {results}"
    [failure] = failures
    assert isinstance(failure, EmailAlreadyTakenError), repr(failure)
    # No driver text leaks out: neither the address nor constraint names.
    assert "duplicate key" not in str(failure)
    assert email not in str(failure)
    async with AsyncSession(db_engine) as session:
        count = await session.scalar(
            select(func.count()).select_from(UserModel).where(UserModel.email == email),
        )
    assert count == 1
