"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

# True when downgrade() loses data: it then calls vld.migrator.ops.irreversible
# and the stairway test does not run it.
irreversible = False


def upgrade() -> None:
    """Apply the revision."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Undo the revision."""
    ${downgrades if downgrades else "pass"}