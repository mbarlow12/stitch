from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a3f5c2e9b1d4"
down_revision = "790b2078d706"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("og_field_resource_source_priority")
    op.create_table(
        "og_field_resource_source_priority",
        sa.Column(
            "resource_id",
            sa.BigInteger()
            .with_variant(sa.BIGINT(), "postgresql")
            .with_variant(sa.INTEGER(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "source_pk",
            sa.BigInteger()
            .with_variant(sa.BIGINT(), "postgresql")
            .with_variant(sa.INTEGER(), "sqlite"),
            nullable=False,
        ),
        sa.Column("colname", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("last_updated_by_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "colname IN ('name', 'country', 'name_local', 'state_province', 'region', 'basin', 'reservoir_formation', 'location_type', 'production_conventionality', 'primary_hydrocarbon_group', 'field_status', 'latitude', 'longitude', 'discovery_year', 'production_start_year', 'fid_year', 'owners', 'operators')",
            name="ck_field_priority_colname",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["last_updated_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["og_field_resources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source"],
            ["og_field_source_priority.source"],
        ),
        sa.ForeignKeyConstraint(
            ["source_pk"], ["oil_gas_field_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("resource_id", "source_pk", "colname"),
    )


def downgrade() -> None:
    raise RuntimeError(f"Irreversible migration: {revision}")
