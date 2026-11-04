import asyncio
import io

import pypdf
from fastapi import UploadFile

from app.core.errors import APIError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PAGE_COUNT = 40
PDF_MAGIC_BYTES = b"%PDF-"


async def read_and_validate_pdf_stream(file: UploadFile) -> bytes:
    """Stream-read upload file chunks enforcing size cap and magic byte validation."""
    content = bytearray()
    chunk_size = 64 * 1024  # 64 KB

    first_chunk = True
    while chunk := await file.read(chunk_size):
        if first_chunk:
            if not chunk.startswith(PDF_MAGIC_BYTES):
                raise APIError(
                    code="INVALID_PDF_FORMAT",
                    message="Uploaded file is not a valid PDF (invalid magic bytes).",
                    status_code=400,
                )
            first_chunk = False

        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            max_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
            raise APIError(
                code="FILE_TOO_LARGE",
                message=f"Uploaded file exceeds maximum limit of {max_mb} MB.",
                status_code=413,
            )

    if not content:
        raise APIError(
            code="EMPTY_FILE",
            message="Uploaded file is empty.",
            status_code=400,
        )

    return bytes(content)


def _sync_parse_pdf(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Synchronous CPU-bound PDF page extraction using pypdf."""
    stream = io.BytesIO(pdf_bytes)
    try:
        reader = pypdf.PdfReader(stream)
    except Exception as exc:
        raise APIError(
            code="CORRUPT_PDF",
            message=f"Failed to read PDF document: {exc}",
            status_code=400,
        ) from exc

    page_count = len(reader.pages)
    if page_count > MAX_PAGE_COUNT:
        raise APIError(
            code="TOO_MANY_PAGES",
            message=f"PDF has {page_count} pages, exceeding the max of {MAX_PAGE_COUNT} pages.",
            status_code=400,
        )

    pages_data: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        # Clean null characters that Postgres text fields reject
        clean_text = text.replace("\x00", "")
        pages_data.append((idx + 1, clean_text.strip()))

    return pages_data


async def parse_pdf_pages(pdf_bytes: bytes, timeout_seconds: float = 30.0) -> list[tuple[int, str]]:
    """Parse PDF bytes asynchronously in a thread pool with a strict execution timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_sync_parse_pdf, pdf_bytes),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        raise APIError(
            code="PARSING_TIMEOUT",
            message="PDF parsing timed out. Please try a simpler or smaller file.",
            status_code=408,
        ) from exc
