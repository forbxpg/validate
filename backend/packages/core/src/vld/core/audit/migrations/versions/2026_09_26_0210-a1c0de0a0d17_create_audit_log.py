"""Create the append-only audit log.

Revision ID: a1c0de0a0d17
Revises:
Create Date: 2026-09-26

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from vld.core.audit import (
    APPEND_ONLY_FUNCTION,
    APPEND_ONLY_TRIGGER,
    APPEND_ONLY_TRUNCATE_TRIGGER,
    AUDIT_LOG_TABLE_NAME,
    AUDIT_SCHEMA_NAME,
    QUALIFIED_AUDIT_LOG_TABLE_NAME,
)
from vld.migrator.ops import app_role, create_domain_schema, drop_domain_schema

revision = "a1c0de0a0d17"
down_revision = None
branch_labels = None
depends_on = None

irreversible = False


def upgrade() -> None:
    """Apply the revision."""
    create_domain_schema(AUDIT_SCHEMA_NAME)
    _ = op.create_table(
        AUDIT_LOG_TABLE_NAME,
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
            comment="Record number",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When it happened",
        ),
        sa.Column("actor_id", sa.UUID(), nullable=True, comment="Who did it"),
        sa.Column("action", sa.Text(), nullable=False, comment="What happened"),
        sa.Column("target_id", sa.UUID(), nullable=True, comment="Over whom"),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Useful record payload",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log")),
        schema=AUDIT_SCHEMA_NAME,
    )
    # The app role writes and reads the log, never rewrites it; the triggers stop
    # the owner as well, so a correction is a new record.
    table = QUALIFIED_AUDIT_LOG_TABLE_NAME
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM PUBLIC, {app_role()}")
    op.execute(
        f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit log is append-only: % refused', TG_OP;
        END;
        $$
        """,
    )
    op.execute(
        f"""
        CREATE TRIGGER {APPEND_ONLY_TRIGGER}
        BEFORE UPDATE OR DELETE ON {QUALIFIED_AUDIT_LOG_TABLE_NAME}
        FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()
        """,
    )
    op.execute(
        f"""
        CREATE TRIGGER {APPEND_ONLY_TRUNCATE_TRIGGER}
        BEFORE TRUNCATE ON {QUALIFIED_AUDIT_LOG_TABLE_NAME}
        FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()
        """,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_table(AUDIT_LOG_TABLE_NAME, schema=AUDIT_SCHEMA_NAME)
    op.execute(f"DROP FUNCTION {APPEND_ONLY_FUNCTION}()")
    drop_domain_schema(AUDIT_SCHEMA_NAME)
