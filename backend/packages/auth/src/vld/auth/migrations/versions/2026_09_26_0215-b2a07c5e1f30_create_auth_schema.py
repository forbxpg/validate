"""Create the auth schema: accounts, one-time tokens and the outbox.

Revision ID: b2a07c5e1f30
Revises: a1c0de0a0d17
Create Date: 2026-09-26

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from vld.auth.infrastructure.models import (
    OUTBOX,
    OUTBOX_STATUS,
    QUALIFIED_USERS,
    ROLE,
    SCHEMA,
    TOKEN_PURPOSE,
    USERS,
    VERIFICATION_TOKENS,
)
from vld.migrator.ops import create_domain_schema, drop_domain_schema

revision = "b2a07c5e1f30"
down_revision = "a1c0de0a0d17"
branch_labels = None
depends_on = None

irreversible = False

# The attempt count of an outbox row stops at ten; a bigint would say otherwise.
squawk_ignore = ("prefer-bigint-over-int",)

_ROLE = sa.Enum("student", "teacher", name=ROLE, schema=SCHEMA)
_TOKEN_PURPOSE = sa.Enum(
    "email_verify",
    "password_reset",
    name=TOKEN_PURPOSE,
    schema=SCHEMA,
)
_OUTBOX_STATUS = sa.Enum(
    "pending",
    "sending",
    "sent",
    "failed",
    name=OUTBOX_STATUS,
    schema=SCHEMA,
)


def upgrade() -> None:
    """Apply the revision."""
    create_domain_schema(SCHEMA)
    _ = op.create_table(
        USERS,
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False, comment="The email address."),
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="The moment the email was verified.",
        ),
        sa.Column(
            "password_hash",
            sa.Text(),
            nullable=False,
            comment="The hash of the password.",
        ),
        sa.Column("role", _ROLE, nullable=False, comment="The role of the user."),
        sa.Column(
            "is_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Whether the user is an administrator.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Whether the user is active.",
        ),
        sa.Column(
            "tokens_invalidated_after",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="The moment the tokens were invalidated.",
        ),
        sa.Column(
            "first_name_ru",
            sa.Text(),
            nullable=True,
            comment="The first name in Russian.",
        ),
        sa.Column(
            "last_name_ru",
            sa.Text(),
            nullable=True,
            comment="The last name in Russian.",
        ),
        sa.Column(
            "first_name_en",
            sa.Text(),
            nullable=True,
            comment="The first name in English.",
        ),
        sa.Column(
            "last_name_en",
            sa.Text(),
            nullable=True,
            comment="The last name in English.",
        ),
        sa.Column(
            "group_number",
            sa.Text(),
            nullable=True,
            comment="The group number.",
        ),
        sa.Column(
            "institution_name",
            sa.Text(),
            nullable=True,
            comment="The name of the institution.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "email = lower(email)",
            name=op.f("ck_users_email_lower_case"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        VERIFICATION_TOKENS,
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("purpose", _TOKEN_PURPOSE, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{QUALIFIED_USERS}.id"],
            name=op.f("fk_verification_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verification_tokens")),
        sa.UniqueConstraint(
            "token_hash",
            name=op.f("uq_verification_tokens_token_hash"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_auth_verification_tokens_created_at"),
        VERIFICATION_TOKENS,
        ["created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_auth_verification_tokens_user_id"),
        VERIFICATION_TOKENS,
        ["user_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        OUTBOX,
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "event_name",
            sa.Text(),
            nullable=False,
            comment="The name of the event.",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="The payload of the event.",
        ),
        sa.Column(
            "status",
            _OUTBOX_STATUS,
            server_default=sa.text("'pending'"),
            nullable=False,
            comment="The status of the event.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="The moment the event was created.",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="The moment the event was published.",
        ),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="The moment the event was claimed.",
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="The number of attempts to publish the event.",
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="The moment the next attempt to publish the event will be made.",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{OUTBOX}_pending",
        OUTBOX,
        ["id"],
        unique=False,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_table(OUTBOX, schema=SCHEMA)
    op.drop_table(VERIFICATION_TOKENS, schema=SCHEMA)
    op.drop_table(USERS, schema=SCHEMA)
    for enum in (_OUTBOX_STATUS, _TOKEN_PURPOSE, _ROLE):
        enum.drop(op.get_bind())
    drop_domain_schema(SCHEMA)
