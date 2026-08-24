"""Configuración base de pytest y fixtures compartidas."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from omnivoice_api.main import app


@pytest_asyncio.fixture
async def async_client() -> AsyncClient:
    """Cliente HTTP asíncrono para tests de integración."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session")
def event_loop():
    """Fixture para el event loop de asyncio (pytest-asyncio lo maneja automáticamente en versiones recientes)."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Resetea singletons entre tests si es necesario."""
    # Importar aquí para evitar importaciones circulares
    from omnivoice_api.core.omnivoice_engine import OmniVoiceEngine
    
    # Resetear el singleton del engine si existe
    if hasattr(OmniVoiceEngine, "_instance"):
        OmniVoiceEngine._instance = None
    
    yield
    
    # Cleanup post-test si hace falta
    if hasattr(OmniVoiceEngine, "_instance"):
        OmniVoiceEngine._instance = None


@pytest.fixture
def sample_text() -> str:
    """Texto de ejemplo para tests de TTS."""
    return "Hola, esto es una prueba de síntesis de voz."


@pytest.fixture
def sample_voice_id() -> str:
    """ID de voz de ejemplo para tests."""
    return "es-mx-male"
