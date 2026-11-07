"""Add brand_ontologies table for structured rules and human-in-the-loop certification

Revision ID: 0002_add_brand_ontology
Revises: 0001_initial_schema
Create Date: 2026-11-07 06:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_brand_ontology"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brand_ontologies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ontology_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_certified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certified_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_brand_ontologies_document_id",
        "brand_ontologies",
        ["document_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_brand_ontologies_document_id", table_name="brand_ontologies")
    op.drop_table("brand_ontologies")
