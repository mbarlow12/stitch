from __future__ import annotations


revision = "20f3722fdba4"
down_revision = ("a3f5c2e9b1d4", "2445c5141f3d")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise RuntimeError(f"Irreversible migration: {revision}")
