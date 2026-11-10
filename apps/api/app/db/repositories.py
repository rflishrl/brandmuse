"""Database repositories encapsulating query, persistence, and cache interactions."""

import datetime
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.db.cache import (
    invalidate_cached_ontology,
)
from app.db.models import BrandOntology, Document, Generation


class DocumentRepository:
    """Repository handling Document queries, session isolation, and sample access."""

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        document_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        for_mutation: bool = False,
    ) -> Document:
        """Fetch document by ID with session validation and sample mutation protection."""
        stmt = select(Document).where(Document.id == document_id)
        res = await db.execute(stmt)
        doc = res.scalar_one_or_none()

        if not doc:
            raise APIError(
                code="DOCUMENT_NOT_FOUND",
                message="Brand guideline document not found or access denied.",
                status_code=404,
            )

        if session_id is not None and doc.session_id != session_id and not doc.is_sample:
            raise APIError(
                code="DOCUMENT_NOT_FOUND",
                message="Brand guideline document not found or access denied.",
                status_code=404,
            )

        if for_mutation and doc.is_sample:
            raise APIError(
                code="SAMPLE_READ_ONLY",
                message=(
                    "Sample brand guidelines are immutable and cannot be modified or re-extracted."
                ),
                status_code=403,
            )

        return doc

    @staticmethod
    async def get_sample_document(db: AsyncSession) -> Document | None:
        """Retrieve the primary sample brand document if loaded."""
        stmt = select(Document).where(Document.is_sample.is_(True)).limit(1)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_for_session(db: AsyncSession, session_id: uuid.UUID) -> list[Document]:
        """List all documents owned by the active session plus the shared sample brand."""
        stmt = (
            select(Document)
            .where(or_(Document.session_id == session_id, Document.is_sample.is_(True)))
            .order_by(Document.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())


class OntologyRepository:
    """Repository handling structured BrandOntology persistence, updates, and cache eviction."""

    @staticmethod
    async def get_by_document_id(
        db: AsyncSession,
        document_id: uuid.UUID,
    ) -> BrandOntology | None:
        """Fetch the BrandOntology entity for a given document."""
        stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        document_id: uuid.UUID,
        ontology_data: dict[str, Any],
    ) -> BrandOntology:
        """Create or update a BrandOntology record and invalidate memory cache."""
        stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        now = datetime.datetime.now(datetime.UTC)
        if not existing:
            record = BrandOntology(
                id=uuid.uuid4(),
                document_id=document_id,
                ontology_data=ontology_data,
                is_certified=False,
                created_at=now,
                updated_at=now,
            )
            db.add(record)
        else:
            existing.ontology_data = ontology_data
            existing.updated_at = now
            record = existing

        await db.commit()
        invalidate_cached_ontology(document_id)
        await db.refresh(record)
        return record

    @staticmethod
    async def update_data(
        db: AsyncSession,
        document_id: uuid.UUID,
        ontology_data: dict[str, Any],
    ) -> BrandOntology:
        """Update existing ontology data and evict from cache."""
        stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise APIError(
                code="ONTOLOGY_NOT_FOUND",
                message="Cannot update ontology: it has not been extracted yet.",
                status_code=404,
            )

        record.ontology_data = ontology_data
        record.updated_at = datetime.datetime.now(datetime.UTC)

        await db.commit()
        invalidate_cached_ontology(document_id)
        await db.refresh(record)
        return record

    @staticmethod
    async def certify(
        db: AsyncSession,
        document_id: uuid.UUID,
        certified_by: str,
    ) -> BrandOntology:
        """Certify brand ontology, mark timestamp, and evict from cache."""
        stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise APIError(
                code="ONTOLOGY_NOT_FOUND",
                message="Cannot certify ontology: it has not been extracted yet.",
                status_code=404,
            )

        now = datetime.datetime.now(datetime.UTC)
        record.is_certified = True
        record.certified_at = now
        record.certified_by = certified_by
        record.updated_at = now

        await db.commit()
        invalidate_cached_ontology(document_id)
        await db.refresh(record)
        return record


class GenerationRepository:
    """Repository handling campaign Generation asset records."""

    @staticmethod
    async def list_for_session(db: AsyncSession, session_id: uuid.UUID) -> list[Generation]:
        """Fetch all image generation assets for a user session, newest first."""
        stmt = (
            select(Generation)
            .where(Generation.session_id == session_id)
            .order_by(Generation.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        session_id: uuid.UUID,
        concept_data: dict[str, Any],
        image_url: str,
        provider: str,
    ) -> Generation:
        """Persist a new campaign image generation record."""
        generation = Generation(
            id=uuid.uuid4(),
            session_id=session_id,
            concept_json=concept_data,
            image_url=image_url,
            provider=provider,
        )
        db.add(generation)
        await db.commit()
        await db.refresh(generation)
        return generation
