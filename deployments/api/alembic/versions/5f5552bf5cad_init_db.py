"""init db

Revision ID: 5f5552bf5cad
Revises:
Create Date: 2026-05-13 14:01:28.082796

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from stitch.api.db.model import StitchBase


# revision identifiers, used by Alembic.
revision: str = "5f5552bf5cad"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    StitchBase.metadata.create_all()


def downgrade() -> None:
    """Downgrade schema."""
    pass
