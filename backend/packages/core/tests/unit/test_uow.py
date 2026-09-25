"""The unit of work commits only when asked and rolls back everything else."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from vld.core.database import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _Session:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")

    async def flush(self) -> None:
        self.calls.append("flush")


def _unit_of_work(session: _Session) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(cast("AsyncSession", cast("object", session)))


async def test_leaving_the_block_rolls_back_what_was_not_committed() -> None:
    """A use case that forgot to commit leaves nothing behind."""
    session = _Session()

    async with _unit_of_work(session):
        pass

    assert session.calls == ["rollback"]


async def test_flush_and_commit_reach_the_session_in_order() -> None:
    """The rollback on exit after a commit has nothing left to undo."""
    session = _Session()

    async with _unit_of_work(session) as uow:
        await uow.flush()
        await uow.commit()

    assert session.calls == ["flush", "commit", "rollback"]


async def test_an_error_inside_the_block_rolls_back_and_propagates() -> None:
    """The unit of work never swallows the error of the use case."""
    session = _Session()
    msg = "use case failed"

    with pytest.raises(RuntimeError, match=msg):
        async with _unit_of_work(session):
            raise RuntimeError(msg)

    assert session.calls == ["rollback"]
