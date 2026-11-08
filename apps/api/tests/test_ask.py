import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.chains.ask import stream_ask_chain
from app.db.models import Document
from app.rag.rrf import FusedResult
from app.schemas.chat import ChatMessage


@pytest.mark.asyncio
async def test_stream_ask_chain_emits_tokens_and_citations() -> None:
    """Verify stream_ask_chain retrieves chunks, streams LLM tokens, and emits citations."""
    session_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        session_id=session_id,
        filename="Aura Living.pdf",
        page_count=6,
        is_sample=True,
    )

    mock_db = AsyncMock()
    mock_db_res = MagicMock()
    mock_db_res.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.return_value = mock_db_res

    mock_chunks = [
        FusedResult(
            item_id=str(uuid.uuid4()),
            rrf_score=0.032,
            vector_score=0.88,
            keyword_score=0.45,
            vector_rank=1,
            keyword_rank=2,
            metadata={"page": 2, "chunk_index": 1, "content": "Our tone is calm and articulate."},
        )
    ]

    mock_req = MagicMock()
    mock_req.is_disconnected = AsyncMock(return_value=False)

    async def mock_astream(*_args, **_kwargs):
        for token in ["Our", " tone", " is", " calm", " [p. 2]."]:
            chunk = MagicMock()
            chunk.content = token
            yield chunk

    mock_llm = MagicMock()
    mock_llm.astream = mock_astream

    with (
        patch("app.chains.ask.hybrid_retrieve", AsyncMock(return_value=mock_chunks)),
        patch("app.chains.ask.get_llm", return_value=mock_llm),
    ):
        events: list[str] = []
        async for sse_event in stream_ask_chain(
            db=mock_db,
            session_id=session_id,
            document_id=doc_id,
            message="What is the tone of voice?",
            history=[ChatMessage(role="user", content="Hi")],
            request=mock_req,
        ):
            events.append(sse_event)

        # Verify token events
        token_events = [e for e in events if e.startswith("event: token")]
        assert len(token_events) == 5

        # Verify final done event
        done_events = [e for e in events if e.startswith("event: done")]
        assert len(done_events) == 1

        done_json_str = done_events[0].replace("event: done\ndata: ", "").strip()
        done_payload = json.loads(done_json_str)

        assert "citations" in done_payload
        assert len(done_payload["citations"]) == 1
        citation = done_payload["citations"][0]
        assert citation["page"] == 2
        assert "calm and articulate" in citation["snippet"]
        assert citation["rrf_score"] == 0.032
        assert "suggested_follow_ups" in done_payload
        assert len(done_payload["suggested_follow_ups"]) > 0


@pytest.mark.asyncio
async def test_stream_ask_chain_missing_document_returns_error_event() -> None:
    """Verify document not found results in an error event."""
    mock_db = AsyncMock()
    mock_db_res = MagicMock()
    mock_db_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_db_res

    mock_req = MagicMock()

    events: list[str] = []
    async for sse_event in stream_ask_chain(
        db=mock_db,
        session_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        message="Hello",
        history=[],
        request=mock_req,
    ):
        events.append(sse_event)

    assert len(events) == 1
    assert events[0].startswith("event: error")
    assert "DOCUMENT_NOT_FOUND" in events[0]
