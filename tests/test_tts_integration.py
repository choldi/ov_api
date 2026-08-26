"""Tests de integración para los endpoints TTS."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from omnivoice_api.main import app


@pytest.fixture
def mock_tts_service() -> AsyncMock:
    """Servicio TTS mockeado para tests de integración."""
    service = AsyncMock()
    service.synthesize_stock.return_value = AsyncMock(
        wav_bytes=b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00",
        duration_sec=0.5,
        sample_rate=22050
    )
    return service


@pytest.mark.asyncio
async def test_tts_endpoint_success(mock_tts_service: AsyncMock) -> None:
    """Test de éxito del endpoint TTS."""
    with patch("omnivoice_api.api.v1.tts.get_tts_service", return_value=mock_tts_service):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "es-mx-male",
                    "language": "es",
                    "speed": 1.0
                }
            )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"


@pytest.mark.asyncio
async def test_tts_endpoint_voice_not_found() -> None:
    """Test de error 404 cuando la voz no se encuentra."""
    from omnivoice_api.core.exceptions import VoiceNotFoundError
    
    async def mock_get_tts_service():
        service = AsyncMock()
        service.synthesize_stock.side_effect = VoiceNotFoundError("voz-inexistente", "stock")
        return service
    
    with patch("omnivoice_api.api.v1.tts.get_tts_service", side_effect=mock_get_tts_service):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "voz-inexistente",
                    "language": "es"
                }
            )
    
    assert response.status_code == 404
    assert "voz-inexistente" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tts_endpoint_unsupported_language() -> None:
    """Test de error 400 cuando el idioma no está soportado."""
    from omnivoice_api.core.exceptions import UnsupportedLanguageError
    
    async def mock_get_tts_service():
        service = AsyncMock()
        service.synthesize_stock.side_effect = UnsupportedLanguageError("xx", ["es", "en"])
        return service
    
    with patch("omnivoice_api.api.v1.tts.get_tts_service", side_effect=mock_get_tts_service):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "es-mx-male",
                    "language": "xx"
                }
            )
    
    assert response.status_code == 400
    assert "xx" in response.json()["detail"]


@pytest.mark.asyncio
async def test_voices_endpoint_success() -> None:
    """Test de éxito del endpoint de voces."""
    from omnivoice_api.core.engine_client import StockVoice
    
    mock_voices = [
        StockVoice(voice_id="es-mx-male", language="es", gender="male", name="Spanish MX Male"),
        StockVoice(voice_id="en-us-male", language="en", gender="male", name="English US Male")
    ]
    
    async def mock_get_engine_client():
        client = AsyncMock()
        client.list_stock_voices.return_value = mock_voices
        return client
    
    with patch("omnivoice_api.api.v1.voices.get_engine_client", side_effect=mock_get_engine_client):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/voices/stock?language=es")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["voice_id"] == "es-mx-male"
    assert data[0]["language"] == "es"
    assert data[0]["gender"] == "male"
    assert data[0]["name"] == "Spanish MX Male"


@pytest.mark.asyncio
async def test_voices_endpoint_no_filter() -> None:
    """Test del endpoint de voces sin filtro de idioma."""
    from omnivoice_api.core.engine_client import StockVoice
    
    mock_voices = [
        StockVoice(voice_id="es-mx-male", language="es", gender="male", name="Spanish MX Male"),
        StockVoice(voice_id="en-us-male", language="en", gender="male", name="English US Male")
    ]
    
    async def mock_get_engine_client():
        client = AsyncMock()
        client.list_stock_voices.return_value = mock_voices
        return client
    
    with patch("omnivoice_api.api.v1.voices.get_engine_client", side_effect=mock_get_engine_client):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/voices/stock")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    voice_ids = [v["voice_id"] for v in data]
    assert "es-mx-male" in voice_ids
    assert "en-us-male" in voice_ids
