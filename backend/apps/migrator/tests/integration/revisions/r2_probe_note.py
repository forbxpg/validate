"""Add a nullable note: an expand step the old code survives.

Revision ID: r2
Revises: r1
Create Date: 2026-09-25

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r2"
down_revision = "r1"
branch_labels = None
depends_on = None

irreversible = False


def upgrade() -> None:
    """Apply the revision."""
    op.add_column("items", sa.Column("note", sa.Text(), nullable=True), schema="probe")


def downgrade() -> None:
    """Undo the revision."""
    op.drop_column("items", "note", schema="probe")
