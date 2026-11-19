import io

import pytest
from fastapi import UploadFile

from app.core.errors import APIError
from app.rag.parse import (
    MAX_UPLOAD_BYTES,
    _sync_parse_pdf,
    read_and_validate_pdf_stream,
)


@pytest.mark.asyncio
async def test_rejects_non_pdf_magic_bytes() -> None:
    """Ensure non-PDF files (e.g. text/exe/zip) are immediately rejected by magic bytes."""
    fake_file = UploadFile(
        file=io.BytesIO(b"Hello world, this is a plain text file not a PDF"),
        filename="test.txt",
    )
    with pytest.raises(APIError) as exc_info:
        await read_and_validate_pdf_stream(fake_file)

    assert exc_info.value.code == "INVALID_PDF_FORMAT"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_rejects_empty_file() -> None:
    """Ensure zero-byte uploads are rejected."""
    empty_file = UploadFile(file=io.BytesIO(b""), filename="empty.pdf")
    with pytest.raises(APIError) as exc_info:
        await read_and_validate_pdf_stream(empty_file)

    assert exc_info.value.code == "EMPTY_FILE"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_rejects_oversized_file() -> None:
    """Ensure files exceeding 10MB are aborted early during streaming."""
    oversized_bytes = b"%PDF-" + b"0" * (MAX_UPLOAD_BYTES + 1024)
    oversized_file = UploadFile(file=io.BytesIO(oversized_bytes), filename="huge.pdf")

    with pytest.raises(APIError) as exc_info:
        await read_and_validate_pdf_stream(oversized_file)

    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert exc_info.value.status_code == 413


def test_rejects_too_many_pages() -> None:
    """Ensure PDF with > 40 pages raises TOO_MANY_PAGES error."""
    import pypdf

    writer = pypdf.PdfWriter()
    # Add 45 blank pages
    for _ in range(45):
        writer.add_blank_page(width=72, height=72)

    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    with pytest.raises(APIError) as exc_info:
        _sync_parse_pdf(pdf_bytes)

    assert exc_info.value.code == "TOO_MANY_PAGES"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_parse_pdf_pages_vision_enrichment_for_sparse_pages() -> None:
    """Verify parse_pdf_pages enriches sparse pages when vision transcription is available."""
    from unittest.mock import AsyncMock, patch

    from app.rag.parse import parse_pdf_pages

    fake_pdf = b"%PDF-1.4\n%fake"
    mock_pages = [(1, "Sparse text")]
    mock_images = {1: b"fake_png_data"}

    with (
        patch("app.rag.parse._sync_parse_pdf", return_value=mock_pages),
        patch("app.rag.parse._extract_sparse_page_images", return_value=mock_images),
        patch("app.rag.parse.settings") as mock_settings,
        patch(
            "app.rag.parse.extract_text_from_image_bytes",
            AsyncMock(return_value="Color Palette: Terracotta #D2691E"),
        ),
    ):
        mock_settings.GEMINI_API_KEY = "fake-key"
        mock_settings.OPENAI_API_KEY = None

        result = await parse_pdf_pages(fake_pdf)
        assert len(result) == 1
        page_num, text = result[0]
        assert page_num == 1
        assert "Sparse text" in text
        assert "Terracotta #D2691E" in text
        assert "[Visual Brand Elements / Diagram OCR]:" in text


def test_get_sample_pdf_path_resolves_single_source_asset() -> None:
    """Verify get_sample_pdf_path resolves the canonical PDF inside app/assets."""
    from app.services.sample_seed import get_sample_pdf_path

    found = get_sample_pdf_path()
    assert found is not None
    assert found.name == "sample-brand-guideline.pdf"
    assert found.parent.name == "assets"
    assert found.is_file()


@pytest.mark.asyncio
async def test_ensure_sample_brand_seeded_handles_concurrent_integrity_error() -> None:
    """Verify ensure_sample_brand_seeded recovers gracefully on concurrent IntegrityError."""
    import datetime
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    from sqlalchemy.exc import IntegrityError

    from app.db.models import Document
    from app.services.sample_seed import ensure_sample_brand_seeded

    winner_doc = Document(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        filename="Aura Living - Brand Guidelines.pdf",
        page_count=6,
        is_sample=True,
        created_at=datetime.datetime.now(datetime.UTC),
    )

    mock_db = AsyncMock()
    mock_db.rollback = AsyncMock()

    with (
        patch(
            "app.services.sample_seed.DocumentRepository.get_sample_document",
            AsyncMock(side_effect=[None, None, winner_doc]),
        ),
        patch(
            "app.services.sample_seed.ingest_pdf_document",
            AsyncMock(
                side_effect=IntegrityError("INSERT", {}, Exception("uq_documents_single_sample"))
            ),
        ),
        patch(
            "app.services.sample_seed.get_sample_pdf_path",
            return_value=MagicMock(read_bytes=MagicMock(return_value=b"%PDF-1.4\n")),
        ),
    ):
        doc, chunk_count = await ensure_sample_brand_seeded(mock_db)

    assert doc.id == winner_doc.id
    assert chunk_count == 0
    mock_db.rollback.assert_awaited_once()
