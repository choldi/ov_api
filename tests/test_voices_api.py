"""Tests de integración para los endpoints de voces."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from omnivoice_api.main import app
from omnivoice_api.api.v1.voices import get_engine_client, get_voice_service
from omnivoice_api.core.engine_client import StockVoice
from omnivoice_api.core.exceptions import (
    InvalidReferenceAudioError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)


@pytest.fixture
def mock_voice_service() -> AsyncMock:
    """Servicio de voces mockeado."""
    service = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_list_cloned_voices() -> None:
    """Test de listado de voces clonadas."""
    mock_service = AsyncMock()
    mock_service.list_voices.return_value = [
        {"id": "1", "name": "voice1", "language": "es"},
        {"id": "2", "name": "voice2", "language": "en"},
    ]

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/voices/cloned")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_cloned_voices_with_language_filter() -> None:
    """Test de listado de voces clonadas con filtro de idioma."""
    mock_service = AsyncMock()
    mock_service.list_voices.return_value = [
        {"id": "1", "name": "voice1", "language": "es"},
    ]

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/voices/cloned?language=es")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_cloned_voice_success() -> None:
    """Test de obtener voz clonada por ID."""
    mock_service = AsyncMock()
    mock_service.get_voice.return_value = {"id": "test-id", "name": "voice1", "language": "es"}

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/voices/cloned/test-id")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_cloned_voice_not_found() -> None:
    """Test de obtener voz clonada inexistente."""
    mock_service = AsyncMock()
    mock_service.get_voice.side_effect = VoiceNotFoundError("test-id")

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/voices/cloned/test-id")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_cloned_voice_success() -> None:
    """Test de eliminar voz clonada exitosamente."""
    mock_service = AsyncMock()
    mock_service.delete_voice.return_value = True

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/voices/cloned/test-id")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_cloned_voice_not_found() -> None:
    """Test de eliminar voz clonada inexistente."""
    mock_service = AsyncMock()
    mock_service.delete_voice.side_effect = VoiceNotFoundError("test-id")

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/voices/cloned/test-id")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_cloned_voice_returns_false() -> None:
    """Test de eliminar voz clonada que retorna False."""
    mock_service = AsyncMock()
    mock_service.delete_voice.return_value = False

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/voices/cloned/test-id")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clone_voice_success_endpoint() -> None:
    """Test de clonación de voz a través del endpoint."""
    mock_service = AsyncMock()
    mock_service.clone_voice.return_value = "new-voice-id"

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a minimal WAV file for upload
            import io
            import wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(22050)
                wav_file.writeframes(b"\x00\x00" * 22050)
            wav_bytes = wav_buffer.getvalue()

            response = await client.post(
                "/api/v1/voices/clone",
                data={"name": "test-voice", "language": "es"},
                files={"reference_audio": ("test.wav", wav_bytes, "audio/wav")},
            )
        assert response.status_code == 201
        data = response.json()
        assert data["voice_id"] == "new-voice-id"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clone_voice_no_filename() -> None:
    """Test de clonación sin nombre de archivo."""
    mock_service = AsyncMock()

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/voices/clone",
                data={"name": "test-voice", "language": "es"},
                files={"reference_audio": ("", b"data", "audio/wav")},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clone_voice_conflict() -> None:
    """Test de clonación con nombre duplicado (conflicto)."""
    mock_service = AsyncMock()
    mock_service.clone_voice.side_effect = ValueError("Voice with name 'test' already exists")

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            import io
            import wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(22050)
                wav_file.writeframes(b"\x00\x00" * 22050)
            wav_bytes = wav_buffer.getvalue()

            response = await client.post(
                "/api/v1/voices/clone",
                data={"name": "test", "language": "es"},
                files={"reference_audio": ("test.wav", wav_bytes, "audio/wav")},
            )
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clone_voice_unsupported_language() -> None:
    """Test de clonación con idioma no soportado."""
    mock_service = AsyncMock()
    mock_service.clone_voice.side_effect = UnsupportedLanguageError("xx", ["es", "en"])

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            import io
            import wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(22050)
                wav_file.writeframes(b"\x00\x00" * 22050)
            wav_bytes = wav_buffer.getvalue()

            response = await client.post(
                "/api/v1/voices/clone",
                data={"name": "test", "language": "xx"},
                files={"reference_audio": ("test.wav", wav_bytes, "audio/wav")},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clone_voice_invalid_audio() -> None:
    """Test de clonación con audio inválido."""
    mock_service = AsyncMock()
    mock_service.clone_voice.side_effect = InvalidReferenceAudioError("Bad audio")

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            import io
            import wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(22050)
                wav_file.writeframes(b"\x00\x00" * 22050)
            wav_bytes = wav_buffer.getvalue()

            response = await client.post(
                "/api/v1/voices/clone",
                data={"name": "test", "language": "es"},
                files={"reference_audio": ("test.wav", wav_bytes, "audio/wav")},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clone_voice_internal_error() -> None:
    """Test de clonación con error interno."""
    mock_service = AsyncMock()
    mock_service.clone_voice.side_effect = RuntimeError("Unexpected")

    async def override():
        yield mock_service

    app.dependency_overrides[get_voice_service] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            import io
            import wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(22050)
                wav_file.writeframes(b"\x00\x00" * 22050)
            wav_bytes = wav_buffer.getvalue()

            response = await client.post(
                "/api/v1/voices/clone",
                data={"name": "test", "language": "es"},
                files={"reference_audio": ("test.wav", wav_bytes, "audio/wav")},
            )
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()
