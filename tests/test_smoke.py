"""Test smoke para verificar que la API arranca y responde correctamente."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok_and_gpu_status(async_client: AsyncClient):
    """Verifica que /api/v1/health responde 200 con status ok y campo gpu."""
    response = await async_client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ok"
    assert "gpu" in data
    assert isinstance(data["gpu"], bool)
    assert "version" in data
    assert "device" in data


@pytest.mark.asyncio
async def test_liveness_endpoint(async_client: AsyncClient):
    """Verifica que /api/v1/health/live responde 200."""
    response = await async_client.get("/api/v1/health/live")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_endpoint(async_client: AsyncClient):
    """Verifica que /api/v1/health/ready responde (puede ser 200 o 503 según checks)."""
    response = await async_client.get("/api/v1/health/ready")
    
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "checks" in data
