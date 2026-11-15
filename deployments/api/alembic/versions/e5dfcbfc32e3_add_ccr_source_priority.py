
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e5dfcbfc32e3"
down_revision = "f3fb36006ce6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE og_field_source_priority SET priority = 5 WHERE source = 'llm'")
    )
    op.bulk_insert(
        sa.table(
            "og_field_source_priority",
            sa.column("source", sa.String),
            sa.column("priority", sa.Integer),
        ),
        [{"source": "ccr", "priority": 4}],
    )


def downgrade() -> None:
    raise RuntimeError(f"Irreversible migration: {revision}")
