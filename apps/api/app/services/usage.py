import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.logging import hash_session_id, slogger
from app.db.models import Generation, UsageCounter


async def check_daily_usage_available(
    db: AsyncSession,
    kind: str,
    limit: int,
) -> None:
    """Read-only daily quota check before generating or uploading assets."""
    today = datetime.date.today()
    stmt = select(UsageCounter.count).where(
        UsageCounter.day == today,
        UsageCounter.kind == kind,
    )
    result = await db.execute(stmt)
    count = result.scalar_one_or_none() or 0

    if count >= limit:
        slogger.warning("daily_quota_exceeded", kind=kind, count=count, limit=limit)
        raise APIError(
            code="DAILY_QUOTA_EXCEEDED",
            message=(
                f"Global daily {kind.upper()} limit ({limit} calls) has been reached. "
                "The demo is currently operating in read-only mode to prevent overage. "
                "Counters reset daily at midnight."
            ),
            status_code=429,
        )


async def check_and_increment_daily_usage(
    db: AsyncSession,
    kind: str,
    limit: int,
) -> int:
    """Check and atomically increment daily usage counters persisted in PostgreSQL.

    Raises APIError (429) if the global daily cap has been reached.
    """
    today = datetime.date.today()

    stmt = (
        select(UsageCounter)
        .where(UsageCounter.day == today, UsageCounter.kind == kind)
        .with_for_update()
    )
    result = await db.execute(stmt)
    counter = result.scalar_one_or_none()

    if not counter:
        counter = UsageCounter(day=today, kind=kind, count=1)
        db.add(counter)
    else:
        if counter.count >= limit:
            raise APIError(
                code="DAILY_QUOTA_EXCEEDED",
                message=(
                    f"Global daily {kind.upper()} limit ({limit} calls) has been reached. "
                    "The demo is currently operating in read-only mode to prevent overage. "
                    "Counters reset daily at midnight."
                ),
                status_code=429,
            )
        counter.count += 1

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        stmt = (
            select(UsageCounter)
            .where(UsageCounter.day == today, UsageCounter.kind == kind)
            .with_for_update()
        )
        result = await db.execute(stmt)
        counter = result.scalar_one_or_none()
        if not counter:
            raise
        if counter.count >= limit:
            raise APIError(
                code="DAILY_QUOTA_EXCEEDED",
                message=(
                    f"Global daily {kind.upper()} limit ({limit} calls) has been reached. "
                    "The demo is currently operating in read-only mode to prevent overage. "
                    "Counters reset daily at midnight."
                ),
                status_code=429,
            ) from exc
        counter.count += 1
        await db.commit()

    return counter.count


async def check_session_image_hourly_limit(
    db: AsyncSession,
    session_id: uuid.UUID,
    limit: int = 5,
) -> None:
    """Ensure a single session cannot exceed the hourly generation limit."""
    one_hour_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)

    stmt = select(func.count(Generation.id)).where(
        Generation.session_id == session_id,
        Generation.created_at >= one_hour_ago,
    )
    result = await db.execute(stmt)
    hourly_count = result.scalar() or 0

    if hourly_count >= limit:
        slogger.warning(
            "session_hourly_limit_exceeded",
            session_hash=hash_session_id(str(session_id)),
            hourly_count=hourly_count,
            limit=limit,
        )
        raise APIError(
            code="SESSION_HOURLY_LIMIT_EXCEEDED",
            message=(
                f"Hourly session limit of {limit} image generations reached. "
                "Please wait before generating more images."
            ),
            status_code=429,
        )


async def check_app_storage_quota(
    db: AsyncSession,
    quota_mb: int,
    additional_bytes: int = 0,
) -> tuple[int, int]:
    """Enforce Tier 1 R2 storage cap without exposing internal quota numbers to visitors."""
    stmt = select(func.coalesce(func.sum(Generation.size_bytes), 0))
    result = await db.execute(stmt)
    used_bytes = int(result.scalar() or 0)
    quota_bytes = quota_mb * 1024 * 1024

    if used_bytes + additional_bytes > quota_bytes:
        slogger.warning(
            "storage_quota_exceeded",
            used_bytes=used_bytes,
            additional_bytes=additional_bytes,
            quota_bytes=quota_bytes,
        )
        raise APIError(
            code="STORAGE_QUOTA_EXCEEDED",
            message=(
                "Image generation is temporarily paused while demo storage capacity "
                "is being refreshed. Please try again later."
            ),
            status_code=429,
        )

    return used_bytes, quota_bytes
