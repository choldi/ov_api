"""Tests de integración para el endpoint TTS (cobertura adicional)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from omnivoice_api.main import app
from omnivoice_api.api.v1.tts import get_tts_service
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)


@pytest.mark.asyncio
async def test_tts_endpoint_unsupported_emotion() -> None:
    """Test de error 400 cuando la emoción no está soportada."""
    mock_service = AsyncMock()
    mock_service.synthesize_stock.side_effect = UnsupportedEmotionError("invalid", ["neutral", "happy"])

    async def override():
        yield mock_service

    app.dependency_overrides[get_tts_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "es-mx-male",
                    "language": "es",
                    "emotion": "invalid",
                },
            )
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tts_endpoint_engine_unavailable() -> None:
    """Test de error 503 cuando el engine no está disponible."""
    mock_service = AsyncMock()
    mock_service.synthesize_stock.side_effect = EngineUnavailableError("Engine down")

    async def override():
        yield mock_service

    app.dependency_overrides[get_tts_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "es-mx-male",
                    "language": "es",
                },
            )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tts_endpoint_internal_error() -> None:
    """Test de error 500 para errores inesperados."""
    mock_service = AsyncMock()
    mock_service.synthesize_stock.side_effect = RuntimeError("Unexpected error")

    async def override():
        yield mock_service

    app.dependency_overrides[get_tts_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "es-mx-male",
                    "language": "es",
                },
            )
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tts_endpoint_with_accept_header() -> None:
    """Test de endpoint TTS con cabecera Accept."""
    mock_service = AsyncMock()
    mock_service.synthesize_stock.return_value = AsyncMock(
        wav_bytes=b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00",
        duration_sec=0.5,
        sample_rate=22050,
    )

    async def override():
        yield mock_service

    app.dependency_overrides[get_tts_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "es-mx-male",
                    "language": "es",
                },
                headers={"Accept": "audio/mpeg"},
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tts_endpoint_with_all_params() -> None:
    """Test de endpoint TTS con todos los parámetros."""
    mock_service = AsyncMock()
    mock_service.synthesize_stock.return_value = AsyncMock(
        wav_bytes=b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00",
        duration_sec=0.5,
        sample_rate=22050,
    )

    async def override():
        yield mock_service

    app.dependency_overrides[get_tts_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tts",
                json={
                    "text": "Hola mundo",
                    "voice_id": "es-mx-male",
                    "language": "es",
                    "speed": 1.5,
                    "emotion": "happy",
                    "intensity": 0.8,
                },
            )
        assert response.status_code == 200
        mock_service.synthesize_stock.assert_called_once_with(
            text="Hola mundo",
            voice_id="es-mx-male",
            language="es",
            speed=1.5,
            emotion="happy",
            intensity=0.8,
        )
    finally:
        app.dependency_overrides.clear()
