import asyncio
import io

import pypdf
from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.logging import logger
from app.rag.vision import extract_text_from_image_bytes

settings = get_settings()

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


def _detect_image_mime(image_bytes: bytes) -> str:
    """Detect raster image MIME type from header magic bytes."""
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return "image/png"


def _sync_parse_pdf_with_images(
    pdf_bytes: bytes,
    extract_sparse_images: bool = False,
) -> tuple[list[tuple[int, str]], dict[int, bytes]]:
    """Single-pass synchronous PDF text extraction + optional sparse-page image capture."""
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
    sparse_images: dict[int, bytes] = {}
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        clean_text = text.replace("\x00", "").strip()
        page_num = idx + 1
        pages_data.append((page_num, clean_text))

        if extract_sparse_images and len(clean_text) < 60:
            try:
                images = getattr(page, "images", [])
                if images and len(images) > 0:
                    sparse_images[page_num] = images[0].data
            except Exception:
                pass

    return pages_data, sparse_images


def _sync_parse_pdf(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Synchronous CPU-bound PDF text extraction wrapper."""
    pages_data, _ = _sync_parse_pdf_with_images(pdf_bytes, extract_sparse_images=False)
    return pages_data


async def parse_pdf_pages(
    pdf_bytes: bytes,
    timeout_seconds: float = 30.0,
    enable_vision: bool = True,
) -> list[tuple[int, str]]:
    """Parse PDF bytes in a single pass with timeout and concurrent multimodal OCR fallback."""
    should_extract_images = enable_vision and bool(
        settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
    )

    try:
        pages_data, sparse_images = await asyncio.wait_for(
            asyncio.to_thread(_sync_parse_pdf_with_images, pdf_bytes, should_extract_images),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        raise APIError(
            code="PARSING_TIMEOUT",
            message="PDF parsing timed out. Please try a simpler or smaller file.",
            status_code=408,
        ) from exc

    if not sparse_images:
        return pages_data

    try:
        sem = asyncio.Semaphore(4)

        async def _ocr_page(page_num: int, img_bytes: bytes) -> tuple[int, str]:
            async with sem:
                mime = _detect_image_mime(img_bytes)
                transcription = await extract_text_from_image_bytes(img_bytes, mime_type=mime)
                return page_num, transcription

        ocr_results = await asyncio.gather(
            *(_ocr_page(page_num, img_bytes) for page_num, img_bytes in sparse_images.items())
        )
        transcriptions = {page_num: text for page_num, text in ocr_results if text}
        if not transcriptions:
            return pages_data

        enriched_pages: list[tuple[int, str]] = []
        for page_num, text in pages_data:
            transcription = transcriptions.get(page_num)
            if transcription:
                enriched_text = (
                    f"{text}\n\n[Visual Brand Elements / Diagram OCR]:\n{transcription}".strip()
                )
                enriched_pages.append((page_num, enriched_text))
            else:
                enriched_pages.append((page_num, text))
        return enriched_pages
    except Exception as exc:
        logger.warning("Vision OCR fallback encountered an error, using base text: %s", exc)
        return pages_data
