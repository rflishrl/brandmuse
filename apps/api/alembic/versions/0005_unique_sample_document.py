"""Enforce a single shared sample brand document via partial unique index

Revision ID: 0005_unique_sample_document
Revises: 0004_add_generation_size_bytes
Create Date: 2026-11-20 04:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_unique_sample_document"
down_revision: str | None = "0004_add_generation_size_bytes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Deduplicate any extra sample documents created before uniqueness enforcement
    op.execute(
        sa.text(
            """
            DELETE FROM documents
            WHERE is_sample IS TRUE
              AND id NOT IN (
                  SELECT id
                  FROM documents
                  WHERE is_sample IS TRUE
                  ORDER BY created_at ASC, id ASC
                  LIMIT 1
              )
            """
        )
    )
    op.create_index(
        "uq_documents_single_sample",
        "documents",
        ["is_sample"],
        unique=True,
        postgresql_where=sa.text("is_sample IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_single_sample", table_name="documents")
