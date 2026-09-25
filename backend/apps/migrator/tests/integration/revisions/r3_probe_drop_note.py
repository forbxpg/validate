"""Drop the note: a contract step that loses data.

Revision ID: r3
Revises: r2
Create Date: 2026-09-25

"""

from __future__ import annotations

import os

from alembic import op

from vld.migrator.ops import irreversible as refuse_downgrade

revision = "r3"
down_revision = "r2"
branch_labels = None
depends_on = None

irreversible = True
squawk_ignore = ("ban-drop-column",)

FAIL_ENV = "PROBE_FAIL_R3"
"""Set by a test to make this revision fail after the first two committed."""


def upgrade() -> None:
    """Apply the revision."""
    if os.environ.get(FAIL_ENV):
        msg = "r3 failed on purpose"
        raise RuntimeError(msg)
    op.drop_column("items", "note", schema="probe")


def downgrade() -> None:
    """Undo the revision."""
    refuse_downgrade(revision)
