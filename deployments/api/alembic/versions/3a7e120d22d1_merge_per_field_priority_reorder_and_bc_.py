from __future__ import annotations


revision = "3a7e120d22d1"
down_revision = ("59fafd631c42", "20f3722fdba4")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise RuntimeError(f"Irreversible migration: {revision}")
