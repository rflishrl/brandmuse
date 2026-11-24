import datetime
import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models import UsageCounter
from app.db.repositories import GenerationRepository
from app.db.session import get_db
from app.schemas.images import AdminUsageResponse

settings = get_settings()

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Validate Bearer ADMIN_TOKEN using constant-time comparison."""
    expected = settings.ADMIN_TOKEN
    if not expected:
        raise APIError(
            code="ADMIN_NOT_CONFIGURED",
            message="Admin endpoint is not configured.",
            status_code=503,
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(
            code="UNAUTHORIZED",
            message="Missing or invalid Bearer token.",
            status_code=401,
        )

    provided = authorization[len("Bearer ") :].strip()
    if not provided or not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise APIError(
            code="UNAUTHORIZED",
            message="Invalid admin token.",
            status_code=401,
        )


@router.get(
    "/usage",
    response_model=AdminUsageResponse,
    operation_id="getAdminUsage",
    summary="Inspect BrandMuse R2 storage quota and daily usage counters",
)
async def get_admin_usage(
    _: None = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
) -> AdminUsageResponse:
    """Return Tier 1 storage consumption and daily usage telemetry for administrators."""
    (
        used_bytes,
        total_generations,
        legacy_unknown_size_count,
    ) = await GenerationRepository.get_storage_usage_stats(db)

    today = datetime.datetime.now(datetime.UTC).date()
    stmt = select(UsageCounter).where(UsageCounter.day == today)
    res = await db.execute(stmt)
    counters = {c.kind: c.count for c in res.scalars().all()}

    quota_bytes = settings.R2_APP_QUOTA_MB * 1024 * 1024
    percent_used = round((used_bytes / quota_bytes) * 100.0, 4) if quota_bytes > 0 else 0.0

    return AdminUsageResponse(
        bucket=settings.R2_BUCKET_NAME,
        prefix=settings.normalized_r2_prefix,
        used_bytes=used_bytes,
        quota_bytes=quota_bytes,
        percent_used=percent_used,
        total_generations=total_generations,
        legacy_unknown_size_count=legacy_unknown_size_count,
        daily_image_count=counters.get("image", 0),
        daily_llm_count=counters.get("llm", 0),
    )
