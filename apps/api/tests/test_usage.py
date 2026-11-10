import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import APIError
from app.db.models import UsageCounter
from app.services.usage import (
    check_and_increment_daily_usage,
    check_session_image_hourly_limit,
)


@pytest.mark.asyncio
async def test_check_and_increment_daily_usage_creates_counter() -> None:
    """Verify new counter is initialized when none exists for today."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    count = await check_and_increment_daily_usage(mock_db, "llm", limit=50)

    assert count == 1
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_and_increment_daily_usage_increments_existing() -> None:
    """Verify existing counter is incremented if below limit."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    existing_counter = UsageCounter(day=datetime.date.today(), kind="image", count=4)
    mock_res.scalar_one_or_none.return_value = existing_counter
    mock_db.execute.return_value = mock_res

    count = await check_and_increment_daily_usage(mock_db, "image", limit=10)

    assert count == 5
    assert existing_counter.count == 5
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_and_increment_daily_usage_exceeds_limit_raises_429() -> None:
    """Verify APIError 429 is raised when daily quota is reached."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    existing_counter = UsageCounter(day=datetime.date.today(), kind="llm", count=50)
    mock_res.scalar_one_or_none.return_value = existing_counter
    mock_db.execute.return_value = mock_res

    with pytest.raises(APIError) as exc_info:
        await check_and_increment_daily_usage(mock_db, "llm", limit=50)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "DAILY_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_check_session_image_hourly_limit_allowed() -> None:
    """Verify session is allowed when within hourly generation limit."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = 3
    mock_db.execute.return_value = mock_res

    session_id = uuid.uuid4()
    # Should not raise exception
    await check_session_image_hourly_limit(mock_db, session_id, limit=5)


@pytest.mark.asyncio
async def test_check_session_image_hourly_limit_exceeded_raises_429() -> None:
    """Verify APIError 429 is raised when session exceeds hourly limit."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = 5
    mock_db.execute.return_value = mock_res

    session_id = uuid.uuid4()
    with pytest.raises(APIError) as exc_info:
        await check_session_image_hourly_limit(mock_db, session_id, limit=5)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "SESSION_HOURLY_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_check_and_increment_daily_usage_concurrency_race_handled() -> None:
    """Verify IntegrityError from concurrent insert triggers rollback and lock increment."""
    from sqlalchemy.exc import IntegrityError

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    # First execute: returns None (both see empty row)
    first_res = MagicMock()
    first_res.scalar_one_or_none.return_value = None

    # Second execute: returns the row inserted by the other worker
    second_res = MagicMock()
    winner_counter = UsageCounter(day=datetime.date.today(), kind="llm", count=1)
    second_res.scalar_one_or_none.return_value = winner_counter

    mock_db.execute.side_effect = [first_res, second_res]
    # First commit fails with IntegrityError (duplicate key), second commit succeeds
    mock_db.commit.side_effect = [IntegrityError("stmt", "params", "orig"), None]

    count = await check_and_increment_daily_usage(mock_db, "llm", limit=50)

    assert count == 2
    assert winner_counter.count == 2
    mock_db.rollback.assert_awaited_once()
