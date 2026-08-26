"""Tests unitarios para el servicio TTS."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.services.tts import TtsService


@pytest.fixture
def mock_engine_client() -> MagicMock:
    """Cliente de engine mockeado para tests."""
    client = AsyncMock()
    client.list_stock_voices.return_value = [
        MagicMock(voice_id="es-mx-male", language="es", gender="male", name="Test Voice"),
        MagicMock(voice_id="en-us-male", language="en", gender="male", name="Test Voice 2"),
    ]
    client.list_emotions.return_value = ["neutral", "happy", "sad"]
    client.synthesize_stock.return_value = MagicMock(
        wav_bytes=b"test wav data",
        duration_sec=1.0,
        sample_rate=22050
    )
    return client


@pytest.fixture
def tts_service(mock_engine_client: MagicMock) -> TtsService:
    """Servicio TTS con cliente de engine mockeado."""
    service = TtsService()
    service._engine_client = mock_engine_client
    return service


@pytest.mark.asyncio
async def test_synthesize_stock_success(tts_service: TtsService, mock_engine_client: MagicMock) -> None:
    """Test de síntesis exitosa con voz stock."""
    result = await tts_service.synthesize_stock(
        text="Hola mundo",
        voice_id="es-mx-male",
        language="es",
        speed=1.0,
        emotion="happy",
        intensity=0.8
    )
    
    assert result.wav_bytes == b"test wav data"
    assert result.duration_sec == 1.0
    assert result.sample_rate == 22050
    
    mock_engine_client.synthesize_stock.assert_called_once_with(
        text="Hola mundo",
        voice_id="es-mx-male",
        language="es",
        speed=1.0,
        emotion="happy",
        intensity=0.8
    )


@pytest.mark.asyncio
async def test_synthesize_stock_voice_not_found(tts_service: TtsService, mock_engine_client: MagicMock) -> None:
    """Test de error cuando la voz no se encuentra."""
    mock_engine_client.list_stock_voices.return_value = [
        MagicMock(voice_id="es-mx-male", language="es", gender="male", name="Test Voice")
    ]
    
    with pytest.raises(VoiceNotFoundError) as exc_info:
        await tts_service.synthesize_stock(
            text="Hola mundo",
            voice_id="voz-inexistente",
            language="es"
        )
    
    assert "voz-inexistente" in str(exc_info.value)
    mock_engine_client.synthesize_stock.assert_not_called()


@pytest.mark.asyncio
async def test_synthesize_stock_unsupported_language(tts_service: TtsService, mock_engine_client: MagicMock) -> None:
    """Test de error cuando el idioma no está soportado."""
    with pytest.raises(UnsupportedLanguageError) as exc_info:
        await tts_service.synthesize_stock(
            text="Hola mundo",
            voice_id="es-mx-male",
            language="xx",  # Idioma no soportado
        )
    
    assert "xx" in str(exc_info.value)
    mock_engine_client.synthesize_stock.assert_not_called()


@pytest.mark.asyncio
async def test_synthesize_stock_unsupported_emotion(tts_service: TtsService, mock_engine_client: MagicMock) -> None:
    """Test de error cuando la emoción no está soportada."""
    with pytest.raises(UnsupportedEmotionError) as exc_info:
        await tts_service.synthesize_stock(
            text="Hola mundo",
            voice_id="es-mx-male",
            language="es",
            emotion="emocion-inexistente"
        )
    
    assert "emocion-inexistente" in str(exc_info.value)
    mock_engine_client.synthesize_stock.assert_not_called()


@pytest.mark.asyncio
async def test_synthesize_stock_engine_unavailable(tts_service: TtsService, mock_engine_client: MagicMock) -> None:
    """Test de error cuando el engine no está disponible."""
    mock_engine_client.synthesize_stock.side_effect = EngineUnavailableError("Engine down")
    
    with pytest.raises(EngineUnavailableError):
        await tts_service.synthesize_stock(
            text="Hola mundo",
            voice_id="es-mx-male",
            language="es"
        )


@pytest.mark.asyncio
async def test_tts_service_close(tts_service: TtsService, mock_engine_client: MagicMock) -> None:
    """Test de cierre correcto del servicio."""
    await tts_service.close()
    mock_engine_client.stop.assert_called_once()
