"""Initial database schema with pgvector, RLS, and search indexes

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

settings = get_settings()


def upgrade() -> None:
    # 1. Enable the vector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Documents table
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_documents_session_id", "documents", ["session_id"])

    # 3. Chunks table with embedding and tsvector
    embedding_dim = settings.EMBEDDING_DIM
    fts_config = settings.FTS_CONFIG

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(embedding_dim), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(f"to_tsvector('{fts_config}', content)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_chunks_document_id", "chunks", ["document_id"])
    op.create_index("idx_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
    )

    # 4. Generations table
    op.create_table(
        "generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_generations_session_id", "generations", ["session_id"])

    # 5. Usage counters table
    op.create_table(
        "usage_counters",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("kind", sa.String(length=20), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )

    # 6. Enable Row Level Security (RLS) on all tables (no policies)
    # to lock down public table access
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE generations ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE usage_counters ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("generations")
    op.drop_table("chunks")
    op.drop_table("documents")
