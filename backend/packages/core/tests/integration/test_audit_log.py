"""Журнал аудита против живой PostgreSQL."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from vld.core.audit import AuditAction, AuditEntry
from vld.core.audit._sqlalchemy import SqlAlchemyAuditLog
from vld.core.audit._tables import (
    APPEND_ONLY_TRIGGER,
    APPEND_ONLY_TRUNCATE_TRIGGER,
    AUDIT_LOG_TABLE_NAME,
    AUDIT_SCHEMA_NAME,
    QUALIFIED_AUDIT_LOG_TABLE_NAME,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = f"""
    insert into {QUALIFIED_AUDIT_LOG_TABLE_NAME} (actor_id, action, payload)
    values (:actor_id, :action, '{{}}'::jsonb)
"""  # ruff: ignore[hardcoded-sql-expression]


async def _seed(session: AsyncSession) -> None:
    _ = await session.execute(
        text(_INSERT),
        {"actor_id": str(uuid.uuid4()), "action": AuditAction.LOGIN_SUCCEEDED.value},
    )


@pytest.mark.integration
async def test_the_audit_row_cannot_be_updated(db_session: AsyncSession) -> None:
    await _seed(db_session)

    with pytest.raises(IntegrityError, match="append-only"):
        _ = await db_session.execute(
            text(f"update {QUALIFIED_AUDIT_LOG_TABLE_NAME} set action = 'tampered'"),  # ruff: ignore[hardcoded-sql-expression] -- константа схемы
        )


@pytest.mark.integration
async def test_the_audit_row_cannot_be_deleted(db_session: AsyncSession) -> None:
    await _seed(db_session)
    with pytest.raises(IntegrityError, match="append-only"):
        _ = await db_session.execute(
            text(f"delete from {QUALIFIED_AUDIT_LOG_TABLE_NAME}")  # ruff: ignore[hardcoded-sql-expression]
        )


@pytest.mark.integration
async def test_the_audit_table_cannot_be_truncated(db_session: AsyncSession) -> None:
    await _seed(db_session)
    with pytest.raises(IntegrityError, match="append-only"):
        _ = await db_session.execute(text(f"truncate {QUALIFIED_AUDIT_LOG_TABLE_NAME}"))


@pytest.mark.integration
async def test_both_append_only_triggers_are_installed(
    db_session: AsyncSession,
) -> None:
    rows = await db_session.execute(
        text("""
            select tgname from pg_trigger
            where tgrelid = (
                select c.oid from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = :schema and c.relname = :table
            )
            and not tgisinternal
            order by tgname
        """),
        {"schema": AUDIT_SCHEMA_NAME, "table": AUDIT_LOG_TABLE_NAME},
    )
    assert [row[0] for row in rows] == [
        APPEND_ONLY_TRIGGER,
        APPEND_ONLY_TRUNCATE_TRIGGER,
    ]


@pytest.mark.integration
async def test_the_port_writes_into_the_migrated_schema(
    db_session: AsyncSession,
) -> None:
    actor, target = uuid.uuid4(), uuid.uuid4()
    await SqlAlchemyAuditLog(db_session).record(
        AuditEntry(
            action=AuditAction.LOGIN_FAILED,
            actor_id=actor,
            target_id=target,
            payload={"email": "probe@b.co"},
        ),
    )
    await db_session.flush()
    row = (
        await db_session.execute(
            text(f"""
                select actor_id, action, target_id, payload
                from {QUALIFIED_AUDIT_LOG_TABLE_NAME}
            """)  # ruff: ignore[hardcoded-sql-expression] -- константа схемы
        )
    ).one()
    assert tuple(row) == (actor, "login_failed", target, {"email": "probe@b.co"})
    occurred_at = cast(
        "datetime",
        (
            await db_session.execute(
                text(f"select occurred_at from {QUALIFIED_AUDIT_LOG_TABLE_NAME}")  # ruff: ignore[hardcoded-sql-expression] -- константа схемы
            )
        ).scalar_one(),
    )
    assert occurred_at.tzinfo is not None
