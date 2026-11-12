from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="getHealth",
    summary="Service Health Check",
    description="Returns current server status, active provider names, and database connectivity.",
)
async def check_health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Check database ping and provider status."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    providers = {
        "llm": settings.LLM_PROVIDER,
        "embeddings": settings.EMBEDDING_PROVIDER,
        "image": settings.IMAGE_PROVIDER,
    }

    overall_status: Literal["ok", "degraded", "error"] = (
        "ok" if db_status == "connected" else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        database=db_status,
        providers=providers,
    )
