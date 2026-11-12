import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.chains.ask import stream_ask_chain
from app.core.security import get_session_id
from app.db.session import get_db
from app.schemas.chat import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "",
    operation_id="streamChat",
    summary="Stream Grounded Chat Answer",
    description=(
        "Streams token-by-token answer via Server-Sent Events (SSE) grounded in retrieved "
        "brand guidelines, concluding with citations (page + snippet) and Langfuse trace link."
    ),
    responses={
        200: {
            "description": "Server-Sent Events: 'event: token', 'event: done', 'event: error'",
            "content": {"text/event-stream": {}},
        }
    },
)
async def chat_endpoint(
    chat_req: ChatRequest,
    request: Request,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream guideline-grounded response using Server-Sent Events."""
    event_generator = stream_ask_chain(
        db=db,
        session_id=session_id,
        document_id=chat_req.document_id,
        message=chat_req.message,
        history=chat_req.history,
        mode=chat_req.mode,
        request=request,
    )

    response_headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers=response_headers,
    )
