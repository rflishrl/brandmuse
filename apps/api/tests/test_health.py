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
