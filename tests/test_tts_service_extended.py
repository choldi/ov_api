"""Tests adicionales para el servicio TTS (cubrir paths no testeados)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omnivoice_api.core.engine_client import AudioResult
from omnivoice_api.core.exceptions import (
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.services.tts import TtsService


@pytest.mark.asyncio
async def test_synthesize_stock_fallback_to_stock_voice() -> None:
    """Test de fallback a voz stock cuando la voz clonada no existe."""
    mock_engine = AsyncMock()
    mock_engine.list_stock_voices.return_value = [
        MagicMock(voice_id="es-mx-male", language="es"),
    ]
    mock_engine.list_emotions.return_value = ["neutral"]
    mock_engine.synthesize_stock.return_value = AudioResult(
        wav_bytes=b"wav", duration_sec=1.0, sample_rate=22050,
    )

    mock_voice_service = AsyncMock()
    mock_voice_service.get_voice.side_effect = VoiceNotFoundError("es-mx-male")

    service = TtsService(engine_client=mock_engine, voice_service=mock_voice_service)
    result = await service.synthesize_stock(
        text="Hola",
        voice_id="es-mx-male",
        language="es",
    )
    assert result.wav_bytes == b"wav"
    mock_engine.synthesize_stock.assert_called_once()


@pytest.mark.asyncio
async def test_synthesize_stock_fallback_on_other_exception() -> None:
    """Test de fallback cuando voice_service lanza otra excepción."""
    mock_engine = AsyncMock()
    mock_engine.list_stock_voices.return_value = [
        MagicMock(voice_id="es-mx-male", language="es"),
    ]
    mock_engine.list_emotions.return_value = ["neutral"]
    mock_engine.synthesize_stock.return_value = AudioResult(
        wav_bytes=b"wav", duration_sec=1.0, sample_rate=22050,
    )

    mock_voice_service = AsyncMock()
    mock_voice_service.get_voice.side_effect = RuntimeError("DB error")

    service = TtsService(engine_client=mock_engine, voice_service=mock_voice_service)
    result = await service.synthesize_stock(
        text="Hola",
        voice_id="es-mx-male",
        language="es",
    )
    assert result.wav_bytes == b"wav"


@pytest.mark.asyncio
async def test_synthesize_stock_cloned_voice() -> None:
    """Test de síntesis con voz clonada (voice found in repository)."""
    mock_engine = AsyncMock()
    mock_engine.synthesize_clone.return_value = AudioResult(
        wav_bytes=b"cloned-wav", duration_sec=1.0, sample_rate=22050,
    )

    mock_voice_service = AsyncMock()
    mock_voice_service.get_voice.return_value = {
        "id": "clone-id",
        "language": "es",
        "reference_path": "/path/to/ref.wav",
    }

    service = TtsService(engine_client=mock_engine, voice_service=mock_voice_service)
    result = await service.synthesize_stock(
        text="Hola",
        voice_id="clone-id",
        language="es",
    )
    assert result.wav_bytes == b"cloned-wav"
    mock_engine.synthesize_clone.assert_called_once()


@pytest.mark.asyncio
async def test_synthesize_clone_language_mismatch() -> None:
    """Test de error cuando el idioma no coincide con la voz clonada."""
    mock_engine = AsyncMock()

    mock_voice_service = AsyncMock()
    mock_voice_service.get_voice.return_value = {
        "id": "clone-id",
        "language": "es",
        "reference_path": "/path/to/ref.wav",
    }

    service = TtsService(engine_client=mock_engine, voice_service=mock_voice_service)
    with pytest.raises(UnsupportedLanguageError):
        await service.synthesize_clone(
            text="Hello",
            voice_id="clone-id",
            language="en",
        )


@pytest.mark.asyncio
async def test_synthesize_clone_success() -> None:
    """Test de síntesis con voz clonada exitosa."""
    mock_engine = AsyncMock()
    mock_engine.synthesize_clone.return_value = AudioResult(
        wav_bytes=b"cloned-wav", duration_sec=2.0, sample_rate=22050,
    )

    mock_voice_service = AsyncMock()
    mock_voice_service.get_voice.return_value = {
        "id": "clone-id",
        "language": "es",
        "reference_path": "/path/to/ref.wav",
    }

    service = TtsService(engine_client=mock_engine, voice_service=mock_voice_service)
    result = await service.synthesize_clone(
        text="Hola",
        voice_id="clone-id",
        language="es",
    )
    assert result.wav_bytes == b"cloned-wav"
    mock_engine.synthesize_clone.assert_called_once_with(
        text="Hola",
        reference_audio_path="/path/to/ref.wav",
        language="es",
        emotion=None,
        intensity=None,
    )


@pytest.mark.asyncio
async def test_get_engine_client_creates_new() -> None:
    """Test de que _get_engine_client crea un cliente nuevo si es None."""
    service = TtsService(engine_client=None, voice_service=AsyncMock())
    with patch("omnivoice_api.services.tts.OmniVoiceEngineClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value = mock_instance
        client = await service._get_engine_client()
        assert client is mock_instance
        mock_instance.start.assert_called_once()


@pytest.mark.asyncio
async def test_get_voice_service_creates_new() -> None:
    """Test de que _get_voice_service crea un servicio nuevo si es None."""
    service = TtsService(engine_client=AsyncMock(), voice_service=None)
    with patch("omnivoice_api.services.tts.VoiceService") as MockService:
        mock_instance = AsyncMock()
        MockService.return_value = mock_instance
        vs = await service._get_voice_service()
        assert vs is mock_instance
        mock_instance.initialize.assert_called_once()


@pytest.mark.asyncio
async def test_close_no_engine() -> None:
    """Test de close cuando no hay engine client."""
    service = TtsService(engine_client=None)
    await service.close()  # Should not raise
