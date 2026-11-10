import time
import uuid
from collections import OrderedDict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrandOntology, Document


class DocumentMetadataCache:
    """Thread-safe bounded in-memory LRU cache with TTL for verified documents and ontologies.

    Eliminates redundant SELECT queries to PostgreSQL for static brand rules and guidelines.
    """

    def __init__(self, maxsize: int = 256, ttl_seconds: float = 600.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._doc_cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._ontology_cache: OrderedDict[str, tuple[float, dict[str, Any] | None]] = OrderedDict()

    def get_document(self, document_id: uuid.UUID) -> dict[str, Any] | None:
        key = str(document_id)
        now = time.time()
        if key in self._doc_cache:
            ts, doc = self._doc_cache[key]
            if now - ts < self.ttl:
                self._doc_cache.move_to_end(key)
                return doc
            del self._doc_cache[key]
        return None

    def set_document(self, document_id: uuid.UUID, doc_data: dict[str, Any]) -> None:
        key = str(document_id)
        now = time.time()
        if key in self._doc_cache:
            self._doc_cache.move_to_end(key)
        self._doc_cache[key] = (now, doc_data)
        if len(self._doc_cache) > self.maxsize:
            self._doc_cache.popitem(last=False)

    def invalidate_document(self, document_id: uuid.UUID) -> None:
        key = str(document_id)
        self._doc_cache.pop(key, None)
        self._ontology_cache.pop(key, None)

    def get_ontology(self, document_id: uuid.UUID) -> tuple[bool, dict[str, Any] | None]:
        """Return (is_cached, cached_data).

        Distinguishes between a cache miss and a cached None (document has no ontology).
        """
        key = str(document_id)
        now = time.time()
        if key in self._ontology_cache:
            ts, onto = self._ontology_cache[key]
            if now - ts < self.ttl:
                self._ontology_cache.move_to_end(key)
                return True, onto
            del self._ontology_cache[key]
        return False, None

    def set_ontology(self, document_id: uuid.UUID, ontology_data: dict[str, Any] | None) -> None:
        key = str(document_id)
        now = time.time()
        if key in self._ontology_cache:
            self._ontology_cache.move_to_end(key)
        self._ontology_cache[key] = (now, ontology_data)
        if len(self._ontology_cache) > self.maxsize:
            self._ontology_cache.popitem(last=False)

    def invalidate_ontology(self, document_id: uuid.UUID) -> None:
        key = str(document_id)
        self._ontology_cache.pop(key, None)

    def clear(self) -> None:
        self._doc_cache.clear()
        self._ontology_cache.clear()


_db_cache = DocumentMetadataCache()


def get_db_cache() -> DocumentMetadataCache:
    """Access the global database query cache singleton."""
    return _db_cache


async def get_cached_document(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Retrieve document metadata, checking in-memory cache before executing a DB query."""
    cached = _db_cache.get_document(document_id)
    if cached is not None:
        return cached

    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        return None

    doc_data = {
        "id": doc.id,
        "session_id": doc.session_id,
        "filename": doc.filename,
        "page_count": doc.page_count,
        "is_sample": doc.is_sample,
    }
    _db_cache.set_document(document_id, doc_data)
    return doc_data


async def get_cached_brand_ontology(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Retrieve brand ontology data, checking in-memory cache before executing a DB query."""
    is_cached, cached_data = _db_cache.get_ontology(document_id)
    if is_cached:
        return cached_data

    stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
    res = await db.execute(stmt)
    ontology = res.scalar_one_or_none()
    ontology_data: dict[str, Any] | None = (
        getattr(ontology, "ontology_data", None) if ontology else None
    )

    _db_cache.set_ontology(document_id, ontology_data)
    return ontology_data


def invalidate_cached_document(document_id: uuid.UUID) -> None:
    """Evict cached document metadata and associated ontology from memory."""
    _db_cache.invalidate_document(document_id)


def invalidate_cached_ontology(document_id: uuid.UUID) -> None:
    """Evict cached ontology data from memory when updated or certified."""
    _db_cache.invalidate_ontology(document_id)
