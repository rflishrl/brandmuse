import uuid

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from slowapi.errors import RateLimitExceeded

from app.core.errors import register_exception_handlers
from app.core.security import get_session_id

_test_app = FastAPI()
register_exception_handlers(_test_app)


@_test_app.get("/test-rate-limited")
def rate_limited_endpoint() -> dict[str, str]:
    exc = RateLimitExceeded.__new__(RateLimitExceeded)
    exc.status_code = 429
    exc.detail = "10 per minute"
    raise exc


@_test_app.get("/test-protected")
def protected_endpoint(session_id: uuid.UUID = Depends(get_session_id)) -> dict[str, str]:
    return {"session_id": str(session_id)}


@pytest.mark.asyncio
async def test_session_id_missing_returns_400() -> None:
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-protected")
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "MISSING_SESSION_ID"


@pytest.mark.asyncio
async def test_session_id_invalid_returns_400() -> None:
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-protected", headers={"X-Session-Id": "invalid-uuid"})
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "INVALID_SESSION_ID"


@pytest.mark.asyncio
async def test_session_id_valid_passes() -> None:
    valid_id = str(uuid.uuid4())
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-protected", headers={"X-Session-Id": valid_id})
        assert response.status_code == 200
        assert response.json()["session_id"] == valid_id


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_uniform_error_envelope() -> None:
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-rate-limited")
        assert response.status_code == 429
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "RATE_LIMITED"
        assert "Rate limit exceeded" in data["error"]["message"]
