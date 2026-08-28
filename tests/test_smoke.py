"""Test smoke para verificar que la API arranca y responde correctamente.

Estos tests NO dependen de la instalación externa de OmniVoice: las rutas
externas se redirigen a un tmp_path mediante ``_isolate_external_install``.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(async_client: AsyncClient):
    """Verifica que /api/v1/health responde 200 con status ok y rutas externas."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "version" in data
    assert "device" in data
    assert "install_dir" in data
    assert "venv_dir" in data
    assert "python_bin" in data


@pytest.mark.asyncio
async def test_liveness_endpoint(async_client: AsyncClient):
    """Verifica que /api/v1/health/live responde 200."""
    response = await async_client.get("/api/v1/health/live")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_endpoint_with_isolated_install(async_client: AsyncClient):
    """Verifica que /api/v1/health/ready responde 200 con la instalación aislada."""
    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["install_dir_exists"] is True
    assert data["checks"]["venv_python_exists"] is True


@pytest.mark.asyncio
async def test_readiness_endpoint_without_install(async_client: AsyncClient, monkeypatch):
    """Verifica que /api/v1/health/ready devuelve 503 si la instalación no existe."""
    # Forzamos rutas inexistentes
    monkeypatch.setenv("OMNIVOICE_INSTALL_DIR", "/nope/does/not/exist")
    monkeypatch.setenv("OMNIVOICE_VENV_DIR", "/nope/venv")
    from omnivoice_api.settings import get_settings

    # Reiniciar el singleton para que se relean las env vars
    import omnivoice_api.settings
    omnivoice_api.settings._settings_instance = None

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["install_dir_exists"] is False

    # Reiniciar el singleton nuevamente para limpiar después del test
    import omnivoice_api.settings
    omnivoice_api.settings._settings_instance = None

