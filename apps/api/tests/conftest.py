from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.main import app


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock async database session for isolated unit tests."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.return_value = AsyncMock()
    return mock_session


@pytest.fixture
async def client(mock_db: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    """Async test HTTP client with overridden database dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
