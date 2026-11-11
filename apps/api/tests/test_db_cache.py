import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.cache import (
    DocumentMetadataCache,
    get_cached_brand_ontology,
    get_cached_document,
    get_db_cache,
    invalidate_cached_ontology,
)


def test_document_metadata_cache_lifecycle() -> None:
    cache = DocumentMetadataCache(maxsize=3, ttl_seconds=10.0)
    doc_id = uuid.uuid4()

    assert cache.get_document(doc_id) is None

    cache.set_document(doc_id, {"id": doc_id, "filename": "test.pdf"})
    cached = cache.get_document(doc_id)
    assert cached is not None
    assert cached["filename"] == "test.pdf"

    cache.invalidate_document(doc_id)
    assert cache.get_document(doc_id) is None


def test_ontology_cache_lifecycle() -> None:
    cache = DocumentMetadataCache(maxsize=3, ttl_seconds=10.0)
    doc_id = uuid.uuid4()

    is_cached, data = cache.get_ontology(doc_id)
    assert not is_cached
    assert data is None

    cache.set_ontology(doc_id, {"brand_name": "Acme"})
    is_cached, data = cache.get_ontology(doc_id)
    assert is_cached
    assert data == {"brand_name": "Acme"}

    # Invalidate
    cache.invalidate_ontology(doc_id)
    is_cached, _ = cache.get_ontology(doc_id)
    assert not is_cached


def test_db_cache_ttl_expiration() -> None:
    cache = DocumentMetadataCache(maxsize=10, ttl_seconds=0.01)
    doc_id = uuid.uuid4()
    cache.set_document(doc_id, {"filename": "expire.pdf"})
    time.sleep(0.02)
    assert cache.get_document(doc_id) is None


@pytest.mark.asyncio
async def test_get_cached_document_hits_cache() -> None:
    doc_id = uuid.uuid4()
    global_cache = get_db_cache()
    global_cache.clear()

    mock_db = AsyncMock()
    mock_row = MagicMock()
    mock_row.id = doc_id
    mock_row.session_id = uuid.uuid4()
    mock_row.filename = "aura.pdf"
    mock_row.page_count = 10
    mock_row.is_sample = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_row
    mock_db.execute.return_value = mock_result

    # First call: database query
    doc1 = await get_cached_document(mock_db, doc_id)
    assert doc1 is not None
    assert doc1["filename"] == "aura.pdf"
    assert mock_db.execute.call_count == 1

    # Second call: served from memory cache without query
    doc2 = await get_cached_document(mock_db, doc_id)
    assert doc2 is not None
    assert doc2["filename"] == "aura.pdf"
    assert mock_db.execute.call_count == 1  # call count did not increase


@pytest.mark.asyncio
async def test_get_cached_brand_ontology_and_invalidation() -> None:
    doc_id = uuid.uuid4()
    global_cache = get_db_cache()
    global_cache.clear()

    mock_db = AsyncMock()
    mock_onto = MagicMock()
    mock_onto.ontology_data = {"brand_name": "Aura Living"}

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_onto
    mock_db.execute.return_value = mock_result

    # First call: database query
    onto1 = await get_cached_brand_ontology(mock_db, doc_id)
    assert onto1 == {"brand_name": "Aura Living"}
    assert mock_db.execute.call_count == 1

    # Second call: cached
    onto2 = await get_cached_brand_ontology(mock_db, doc_id)
    assert onto2 == {"brand_name": "Aura Living"}
    assert mock_db.execute.call_count == 1

    # Invalidate
    invalidate_cached_ontology(doc_id)
    onto3 = await get_cached_brand_ontology(mock_db, doc_id)
    assert onto3 == {"brand_name": "Aura Living"}
    assert mock_db.execute.call_count == 2
