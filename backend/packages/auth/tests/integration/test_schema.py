"""The schemas of auth and audit as the migrations build them."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from vld.auth.domain import Role, TokenPurpose
from vld.auth.infrastructure.models import (
    CLAIMABLE_PREDICATE,
    OUTBOX,
    OUTBOX_STATUS,
    QUALIFIED_USERS,
    QUALIFIED_VERIFICATION_TOKENS,
    ROLE,
    SCHEMA,
    TOKEN_PURPOSE,
    OutboxStatus,
    UserModel,
    VerificationTokenModel,
)
from vld.auth.infrastructure.models._outbox import PENDING_PREDICATE
from vld.core.audit import QUALIFIED_AUDIT_LOG_TABLE_NAME

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

_INSERT_USER = text(
    f"""
    insert into {QUALIFIED_USERS} (id, email, password_hash, role)
    values (:id, :email, 'h', 'student')
    """,  # ruff: ignore[hardcoded-sql-expression] -- schema constants
)

_ENUM_LABELS = text("""
    select enumlabel from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    join pg_namespace n on n.oid = t.typnamespace
    where n.nspname = :schema and t.typname = :type_name
    order by e.enumsortorder
""")


async def _labels(session: AsyncSession, type_name: str) -> list[str]:
    rows = await session.execute(
        _ENUM_LABELS,
        {"schema": SCHEMA, "type_name": type_name},
    )
    return [row[0] for row in rows]


async def test_the_domain_schema_holds_only_its_tables(
    db_session: AsyncSession,
) -> None:
    """The auth schema has exactly the tables of the domain."""
    rows = await db_session.execute(
        text(
            """
            select table_name
            from information_schema.tables
            where table_schema = :schema
            order by table_name
            """,
        ),
        {"schema": SCHEMA},
    )

    assert [row[0] for row in rows] == ["outbox", "users", "verification_tokens"]


async def test_an_upper_case_email_is_refused_by_the_database(
    db_session: AsyncSession,
) -> None:
    """The lower-case rule lives in a CHECK, not only in the service."""
    with pytest.raises(IntegrityError, match="ck_users_email_lower_case"):
        _ = await db_session.execute(
            _INSERT_USER,
            {"id": uuid.uuid4(), "email": "Ivan@b.co"},
        )


async def test_an_email_is_unique(db_session: AsyncSession) -> None:
    """Two accounts cannot share an address."""
    _ = await db_session.execute(_INSERT_USER, {"id": uuid.uuid4(), "email": "i@b.co"})

    with pytest.raises(IntegrityError, match="uq_users_email"):
        _ = await db_session.execute(
            _INSERT_USER,
            {"id": uuid.uuid4(), "email": "i@b.co"},
        )


async def test_a_token_needs_an_expiry(db_session: AsyncSession) -> None:
    """The schema refuses a token without an expiry."""
    user_id = uuid.uuid4()
    _ = await db_session.execute(_INSERT_USER, {"id": user_id, "email": "x@b.co"})

    with pytest.raises(IntegrityError):
        _ = await db_session.execute(
            text(
                f"""
                insert into {QUALIFIED_VERIFICATION_TOKENS}
                (user_id, token_hash, purpose, expires_at)
                values (:user_id, 'h', 'email_verify', null)
                """,  # ruff: ignore[hardcoded-sql-expression] -- schema constants
            ),
            {"user_id": user_id},
        )


async def test_enum_labels_are_the_values_of_the_code(db_session: AsyncSession) -> None:
    """The database types spell the values of the enums, not their member names."""
    # Literals: comparing with the enums would compare them with themselves.
    assert await _labels(db_session, ROLE) == ["student", "teacher"]
    assert await _labels(db_session, TOKEN_PURPOSE) == [
        "email_verify",
        "password_reset",
    ]
    assert await _labels(db_session, OUTBOX_STATUS) == [s.value for s in OutboxStatus]


async def test_every_moment_is_timestamptz(db_session: AsyncSession) -> None:
    """A naive column would drop the offset silently."""
    rows = await db_session.execute(
        text(
            """
            select table_name, column_name, data_type
            from information_schema.columns
            where table_schema in (:auth, 'audit')
            and data_type like 'timestamp%'
            """,
        ),
        {"auth": SCHEMA},
    )

    naive = [f"{t}.{c}" for t, c, kind in rows if kind != "timestamp with time zone"]
    assert naive == []


async def test_the_pending_index_matches_the_shared_predicate(
    db_session: AsyncSession,
) -> None:
    """The partial index and the claim query share one predicate."""
    stored = await db_session.scalar(
        text(
            """
            select pg_get_expr(i.indpred, i.indrelid)
            from pg_index i
            join pg_class c on c.oid = i.indexrelid
            join pg_namespace n on n.oid = c.relnamespace
            where c.relname = :name
            and n.nspname = :schema
            """,
        ),
        {"name": f"ix_{OUTBOX}_pending", "schema": SCHEMA},
    )
    normalized = " ".join(
        re.sub(r"::[\w.]+", "", str(stored)).replace("(", "").replace(")", "").split(),
    )

    assert normalized == PENDING_PREDICATE
    assert CLAIMABLE_PREDICATE.startswith(PENDING_PREDICATE)


async def test_orm_models_agree_with_the_migrated_schema(
    db_session: AsyncSession,
) -> None:
    """Writing through the ORM passes the schema the migration built."""
    user = UserModel(
        id=uuid.uuid4(),
        email="orm@probe.co",
        password_hash="h",
        role=Role.TEACHER,
        first_name_ru="Иван",
    )
    db_session.add(user)
    await db_session.flush()
    token = VerificationTokenModel(
        user_id=user.id,
        token_hash="orm-token-hash",
        purpose=TokenPurpose.EMAIL_VERIFY,
        expires_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
        used_at=None,
    )
    db_session.add(token)
    await db_session.flush()
    user_id, token_id = user.id, token.id
    db_session.expire_all()

    stored = await db_session.get(UserModel, user_id)
    assert stored is not None
    assert stored.role is Role.TEACHER
    assert stored.is_active is True
    assert stored.is_admin is False
    assert stored.first_name_ru == "Иван"
    stored_token = await db_session.get(VerificationTokenModel, token_id)
    assert stored_token is not None
    assert stored_token.expires_at == datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


async def test_the_version_table_lives_outside_the_domain_schemas(
    db_session: AsyncSession,
) -> None:
    """The state of the chain belongs to no domain."""
    rows = await db_session.execute(
        text(
            """
            select table_schema
            from information_schema.tables
            where table_name = 'alembic_version'
            """,
        ),
    )

    assert [row[0] for row in rows] == ["vld_meta"]


async def test_the_audit_log_refuses_rewrites(db_session: AsyncSession) -> None:
    """Even the owner cannot change or delete a record."""
    _ = await db_session.execute(
        text(f"insert into {QUALIFIED_AUDIT_LOG_TABLE_NAME} (action) values ('probe')"),  # ruff: ignore[hardcoded-sql-expression] -- schema constants
    )

    with pytest.raises(DBAPIError, match="append-only"):
        _ = await db_session.execute(
            text(f"update {QUALIFIED_AUDIT_LOG_TABLE_NAME} set action = 'x'"),  # ruff: ignore[hardcoded-sql-expression] -- schema constants
        )


async def test_the_app_role_may_not_rewrite_the_audit_log(
    db_session: AsyncSession,
) -> None:
    """The API role writes and reads the log, and nothing more."""
    rows = await db_session.execute(
        text(
            """
            select privilege_type
            from information_schema.role_table_grants
            where grantee = 'vld_test_app'
            and table_schema = 'audit'
            and table_name = 'log'
            """,
        ),
    )

    assert sorted(row[0] for row in rows) == ["INSERT", "SELECT"]
