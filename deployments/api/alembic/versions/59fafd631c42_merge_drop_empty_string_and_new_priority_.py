
from __future__ import annotations


revision = "59fafd631c42"
down_revision = ("2584345b1e0d", "790b2078d706")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise RuntimeError(f"Irreversible migration: {revision}")
