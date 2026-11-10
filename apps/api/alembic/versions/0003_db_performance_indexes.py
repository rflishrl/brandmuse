"""Add composite indexes for chunks table query performance

Revision ID: 0003_db_performance_indexes
Revises: 0002_add_brand_ontology
Create Date: 2026-11-09 18:35:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_db_performance_indexes"
down_revision: str | None = "0002_add_brand_ontology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_chunks_doc_chunk_idx",
        "chunks",
        ["document_id", "chunk_index"],
        unique=False,
    )
    op.create_index(
        "idx_chunks_doc_page",
        "chunks",
        ["document_id", "page"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_chunks_doc_page", table_name="chunks")
    op.drop_index("idx_chunks_doc_chunk_idx", table_name="chunks")
