from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120


@dataclass
class DocumentChunk:
    """Represents a discrete text chunk belonging to a specific page."""

    page: int
    chunk_index: int
    content: str


def chunk_pages(
    pages: list[tuple[int, str]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Split extracted page text into chunks, strictly preserving page boundaries."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[DocumentChunk] = []
    global_chunk_index = 0

    for page_num, page_text in pages:
        if not page_text.strip():
            continue

        raw_chunks = splitter.split_text(page_text)
        for text in raw_chunks:
            stripped = text.strip()
            if stripped:
                chunks.append(
                    DocumentChunk(
                        page=page_num,
                        chunk_index=global_chunk_index,
                        content=stripped,
                    )
                )
                global_chunk_index += 1

    return chunks
