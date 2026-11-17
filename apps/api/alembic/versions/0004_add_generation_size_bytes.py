"""Add nullable size_bytes column to generations for R2 app storage quota tracking

Revision ID: 0004_add_generation_size_bytes
Revises: 0003_db_performance_indexes
Create Date: 2026-11-17 05:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_add_generation_size_bytes"
down_revision: str | None = "0003_db_performance_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "size_bytes")
