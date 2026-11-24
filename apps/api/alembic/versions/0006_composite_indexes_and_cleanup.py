"""Add composite session/created_at indexes and drop redundant duplicate indexes

Revision ID: 0006_composite_indexes_and_cleanup
Revises: 0005_unique_sample_document
Create Date: 2026-11-24 19:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_composite_indexes_and_cleanup"
down_revision: str | None = "0005_unique_sample_document"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_documents_session_created_at",
        "documents",
        ["session_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_generations_session_created_at",
        "generations",
        ["session_id", sa.text("created_at DESC")],
        unique=False,
    )
    # Drop redundant single-column indexes already covered by composite or unique constraints
    op.execute(sa.text("DROP INDEX IF EXISTS idx_chunks_document_id"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_brand_ontologies_document_id"))


def downgrade() -> None:
    op.create_index(
        "idx_brand_ontologies_document_id",
        "brand_ontologies",
        ["document_id"],
        unique=True,
    )
    op.create_index(
        "idx_chunks_document_id",
        "chunks",
        ["document_id"],
        unique=False,
    )
    op.drop_index("idx_generations_session_created_at", table_name="generations")
    op.drop_index("idx_documents_session_created_at", table_name="documents")
