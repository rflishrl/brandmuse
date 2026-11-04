from app.rag.chunk import chunk_pages


def test_chunking_preserves_page_boundaries() -> None:
    """Ensure chunks never merge text from adjacent pages."""
    pages = [
        (1, "Page 1 content. " * 30),
        (2, "Page 2 content. " * 30),
        (3, "Page 3 content. " * 30),
    ]

    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=50)

    assert len(chunks) > 3
    # Check that each chunk only contains content from its declared page
    for chunk in chunks:
        if chunk.page == 1:
            assert "Page 2" not in chunk.content
            assert "Page 3" not in chunk.content
        elif chunk.page == 2:
            assert "Page 1" not in chunk.content
            assert "Page 3" not in chunk.content
        elif chunk.page == 3:
            assert "Page 1" not in chunk.content
            assert "Page 2" not in chunk.content


def test_chunk_index_increases_monotonically() -> None:
    """Ensure chunk_index increments sequentially from 0."""
    pages = [
        (1, "First page text. " * 40),
        (2, "Second page text. " * 40),
    ]
    chunks = chunk_pages(pages, chunk_size=400, chunk_overlap=50)

    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_empty_pages_skipped() -> None:
    """Ensure empty or whitespace-only pages produce no chunks."""
    pages = [
        (1, ""),
        (2, "   \n\n  "),
        (3, "Actual valid content."),
    ]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].page == 3
    assert chunks[0].content == "Actual valid content."
