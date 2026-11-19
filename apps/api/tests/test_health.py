import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_ok(client: AsyncClient) -> None:
    """Verify GET /api/health returns 200 with ok status, database, and providers."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "llm" in data["providers"]
    assert "embeddings" in data["providers"]
    assert "image" in data["providers"]


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    """Verify security headers middleware sets standard hardening headers."""
    response = await client.get("/api/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in response.headers.get("referrer-policy", "")


@pytest.mark.asyncio
async def test_unhandled_500_preserves_cors_headers(mock_db) -> None:
    """Verify unhandled 500 errors include CORS headers for allowed origins."""
    import uuid
    from unittest.mock import patch

    from httpx import ASGITransport

    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            with patch(
                "app.db.repositories.DocumentRepository.list_for_session",
                side_effect=RuntimeError("boom"),
            ):
                response = await ac.get(
                    "/api/documents",
                    headers={
                        "X-Session-Id": str(uuid.uuid4()),
                        "Origin": "http://localhost:5173",
                    },
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "RuntimeError" in response.json()["error"]["message"]
