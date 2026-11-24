import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import APIError
from app.services.usage import (
    check_and_increment_daily_usage,
    check_app_storage_quota,
    check_session_image_hourly_limit,
)


@pytest.mark.asyncio
async def test_check_and_increment_daily_usage_creates_counter() -> None:
    """Verify atomic upsert initializes counter to 1 when none exists for today."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = 1
    mock_db.execute.return_value = mock_res

    count = await check_and_increment_daily_usage(mock_db, "llm", limit=50)

    assert count == 1
    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_and_increment_daily_usage_increments_existing() -> None:
    """Verify atomic upsert returns incremented counter when below limit."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = 5
    mock_db.execute.return_value = mock_res

    count = await check_and_increment_daily_usage(mock_db, "image", limit=10)

    assert count == 5
    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_and_increment_daily_usage_exceeds_limit_raises_429() -> None:
    """Verify APIError 429 is raised when atomic upsert returns None (cap reached)."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    with pytest.raises(APIError) as exc_info:
        await check_and_increment_daily_usage(mock_db, "llm", limit=50)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "DAILY_QUOTA_EXCEEDED"
    mock_db.rollback.assert_awaited_once()


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
async def test_check_and_increment_daily_usage_zero_limit_raises_429() -> None:
    """Verify APIError 429 is raised immediately when limit is 0 without DB round trip."""
    mock_db = AsyncMock()

    with pytest.raises(APIError) as exc_info:
        await check_and_increment_daily_usage(mock_db, "llm", limit=0)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "DAILY_QUOTA_EXCEEDED"
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_app_storage_quota_allows_and_blocks_without_numbers() -> None:
    """Tier 1 storage quota must allow within cap and hide internal numbers on rejection."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = 100 * 1024 * 1024
    mock_db.execute.return_value = mock_res

    used, quota = await check_app_storage_quota(mock_db, quota_mb=2048, additional_bytes=1024)
    assert used == 100 * 1024 * 1024
    assert quota == 2048 * 1024 * 1024

    mock_res.scalar.return_value = 2048 * 1024 * 1024
    with pytest.raises(APIError) as exc_info:
        await check_app_storage_quota(mock_db, quota_mb=2048, additional_bytes=1)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "STORAGE_QUOTA_EXCEEDED"
    assert not any(ch.isdigit() for ch in exc_info.value.message)
