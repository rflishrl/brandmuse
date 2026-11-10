import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.db.models import Generation, UsageCounter


async def check_and_increment_daily_usage(
    db: AsyncSession,
    kind: str,
    limit: int,
) -> int:
    """Check and atomically increment daily usage counters persisted in PostgreSQL.

    Raises APIError (429) if the global daily cap has been reached.
    """
    today = datetime.date.today()

    # Query with row lock for safe concurrent atomic updates
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
        # Resolve concurrent insert race condition by rolling back and re-fetching with lock
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
        raise APIError(
            code="SESSION_HOURLY_LIMIT_EXCEEDED",
            message=(
                f"Hourly session limit of {limit} image generations reached. "
                "Please wait before generating more images."
            ),
            status_code=429,
        )
