
from __future__ import annotations

from alembic import op

revision = "790b2078d706"
down_revision = "f3fb36006ce6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM oil_gas_field_source_values WHERE value_text = ''")
    with op.batch_alter_table("oil_gas_field_source_values") as batch_op:
        batch_op.create_check_constraint(
            "ck_source_value_text_nonempty",
            "value_text <> ''",
        )


def downgrade() -> None:
    raise RuntimeError(f"Irreversible migration: {revision}")
