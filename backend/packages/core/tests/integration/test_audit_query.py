from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from vld.core.audit import AuditAction
from vld.core.audit._sqlalchemy import SqlAlchemyAuditQuery
from vld.core.audit._tables import QUALIFIED_AUDIT_LOG_TABLE_NAME

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = f"""
    insert into {QUALIFIED_AUDIT_LOG_TABLE_NAME} (occurred_at, actor_id, action, target_id, payload)
    values (:occurred_at, :actor_id, :action, :target_id, '{{}}'::jsonb)
"""  # ruff: ignore[hardcoded-sql-expression]

_ACTOR = uuid.uuid4()
_TARGET = uuid.uuid4()

_T0 = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
_T1 = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
_T2 = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


async def _seed(session: AsyncSession) -> None:
    rows = [
        {"occurred_at": _T0, "actor_id": _ACTOR, "target_id": _TARGET},
        {"occurred_at": _T1, "actor_id": _ACTOR, "target_id": uuid.uuid4()},
        {"occurred_at": _T2, "actor_id": uuid.uuid4(), "target_id": _TARGET},
    ]
    for row in rows:
        _ = await session.execute(
            text(_INSERT),
            {
                "occurred_at": row["occurred_at"],
                "actor_id": str(row["actor_id"]),
                "target_id": str(row["target_id"]),
                "action": AuditAction.USER_BANNED.value,
            },
        )


@pytest.mark.integration
async def test_search_filters_by_actor_and_target(db_session: AsyncSession) -> None:
    await _seed(db_session)
    query = SqlAlchemyAuditQuery(db_session)
    by_actor = await query.search(
        actor_id=_ACTOR,
        target_id=None,
        occurred_from=None,
        occurred_to=None,
        limit=10,
        offset=0,
    )
    by_both = await query.search(
        actor_id=_ACTOR,
        target_id=_TARGET,
        occurred_from=None,
        occurred_to=None,
        limit=10,
        offset=0,
    )

    assert by_actor.total == 2
    assert all(record.actor_id == _ACTOR for record in by_actor.records)
    assert by_both.total == 1
    assert by_both.records[0].target_id == _TARGET
    assert by_both.records[0].action == "user_banned"


@pytest.mark.integration
async def test_search_period_is_half_open(db_session: AsyncSession) -> None:
    await _seed(db_session)
    query = SqlAlchemyAuditQuery(db_session)

    window = await query.search(
        actor_id=None,
        target_id=None,
        occurred_from=_T0,
        occurred_to=_T2,
        limit=10,
        offset=0,
    )

    assert window.total == 2
    assert [record.occurred_at for record in window.records] == [_T1, _T0]


@pytest.mark.integration
async def test_search_pages_newest_first_with_total(db_session: AsyncSession) -> None:
    await _seed(db_session)
    query = SqlAlchemyAuditQuery(db_session)

    first = await query.search(
        actor_id=None,
        target_id=None,
        occurred_from=None,
        occurred_to=None,
        limit=2,
        offset=0,
    )
    beyond = await query.search(
        actor_id=None,
        target_id=None,
        occurred_from=None,
        occurred_to=None,
        limit=2,
        offset=2,
    )

    assert first.total == 3
    assert [record.occurred_at for record in first.records] == [_T2, _T1]
    assert [record.id for record in first.records] == sorted(
        (record.id for record in first.records), reverse=True
    )
    assert beyond.total == 3
    assert [record.occurred_at for record in beyond.records] == [_T0]
