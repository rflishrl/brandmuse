import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import APIError
from app.db.models import Document
from app.db.repositories import (
    DocumentRepository,
    GenerationRepository,
    OntologyRepository,
)


@pytest.mark.asyncio
async def test_document_repository_get_by_id_owner() -> None:
    """Verify owner can fetch document."""
    doc_id = uuid.uuid4()
    session_id = uuid.uuid4()
    doc = Document(id=doc_id, session_id=session_id, filename="Brand.pdf", is_sample=False)

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = doc
    mock_db.execute.return_value = mock_res

    res = await DocumentRepository.get_by_id(mock_db, doc_id, session_id=session_id)
    assert res.id == doc_id
    assert res.filename == "Brand.pdf"


@pytest.mark.asyncio
async def test_document_repository_get_by_id_sample_mutation_forbidden() -> None:
    """Verify sample document blocks mutation requests with 403."""
    doc_id = uuid.uuid4()
    session_id = uuid.uuid4()
    sample_doc = Document(id=doc_id, session_id=uuid.uuid4(), filename="Sample.pdf", is_sample=True)

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = sample_doc
    mock_db.execute.return_value = mock_res

    with pytest.raises(APIError) as exc_info:
        await DocumentRepository.get_by_id(
            mock_db, doc_id, session_id=session_id, for_mutation=True
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "SAMPLE_READ_ONLY"


@pytest.mark.asyncio
async def test_document_repository_get_by_id_intruder_forbidden() -> None:
    """Verify other user cannot access private document."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, session_id=uuid.uuid4(), filename="Secret.pdf", is_sample=False)

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = doc
    mock_db.execute.return_value = mock_res

    with pytest.raises(APIError) as exc_info:
        await DocumentRepository.get_by_id(mock_db, doc_id, session_id=uuid.uuid4())

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_document_repository_list_for_session() -> None:
    """Verify listing returns documents for session."""
    session_id = uuid.uuid4()
    doc1 = Document(id=uuid.uuid4(), session_id=session_id, filename="Doc1.pdf", is_sample=False)
    doc2 = Document(id=uuid.uuid4(), session_id=uuid.uuid4(), filename="Sample.pdf", is_sample=True)

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [doc1, doc2]
    mock_db.execute.return_value = mock_res

    docs = await DocumentRepository.list_for_session(mock_db, session_id)
    assert len(docs) == 2


@pytest.mark.asyncio
@patch("app.db.repositories.invalidate_cached_ontology")
async def test_ontology_repository_upsert(mock_invalidate: MagicMock) -> None:
    """Verify OntologyRepository upserts record and invalidates cache."""
    doc_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    record = await OntologyRepository.upsert(mock_db, doc_id, {"identity": {"brand_name": "Test"}})

    assert record.document_id == doc_id
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    mock_invalidate.assert_called_once_with(doc_id)


@pytest.mark.asyncio
async def test_generation_repository_create_and_list() -> None:
    """Verify GenerationRepository create and list operations."""
    session_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    gen = await GenerationRepository.create(
        db=mock_db,
        session_id=session_id,
        concept_data={"title": "Test Concept"},
        image_url="https://r2.dev/img.png",
        provider="mock",
    )

    assert gen.session_id == session_id
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()

    # List generations
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [gen]
    mock_db.execute.return_value = mock_res

    items = await GenerationRepository.list_for_session(mock_db, session_id)
    assert len(items) == 1
    assert items[0].image_url == "https://r2.dev/img.png"
