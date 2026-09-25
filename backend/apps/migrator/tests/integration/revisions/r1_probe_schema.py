"""Create the probe schema and its table.

Revision ID: r1
Revises:
Create Date: 2026-09-25

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from vld.migrator.ops import create_domain_schema, drop_domain_schema

revision = "r1"
down_revision = None
branch_labels = None
depends_on = None

irreversible = False


def upgrade() -> None:
    """Apply the revision."""
    create_domain_schema("probe")
    _ = op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_items"),
        schema="probe",
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_table("items", schema="probe")
    drop_domain_schema("probe")
