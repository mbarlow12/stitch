from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "2445c5141f3d"
down_revision = "e5dfcbfc32e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE og_field_source_priority SET priority = priority + 100"))
    for source, priority in (("rmi", 1), ("wm", 2), ("ccr", 3), ("gem", 4), ("llm", 5)):
        op.execute(
            sa.text(
                "UPDATE og_field_source_priority SET priority = :p WHERE source = :s"
            ).bindparams(p=priority, s=source)
        )


def downgrade() -> None:
    raise RuntimeError(f"Irreversible migration: {revision}")
