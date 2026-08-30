"""Tests unitarios para el cliente del engine OmniVoice."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from omnivoice_api.core.engine_client import (
    AudioResult,
    EngineHealth,
    OmniVoiceEngineClient,
    StockVoice,
)
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)


def _make_wav_bytes(sample_rate: int = 22050, duration_sec: float = 1.0) -> bytes:
    """Genera bytes WAV válidos para tests."""
    import io
    import wave

    num_samples = int(duration_sec * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * num_samples)
    return buffer.getvalue()


@pytest.fixture
def engine_client() -> OmniVoiceEngineClient:
    """Cliente de engine para tests."""
    return OmniVoiceEngineClient()


@pytest.mark.asyncio
async def test_start_and_stop(engine_client: OmniVoiceEngineClient) -> None:
    """Test de start y stop del cliente."""
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_get_engine.return_value = mock_engine
        await engine_client.start()
        assert engine_client._started is True
        assert engine_client._engine is mock_engine

        with patch("omnivoice_api.core.engine_client.close_engine", new_callable=AsyncMock) as mock_close:
            await engine_client.stop()
            assert engine_client._started is False
            assert engine_client._engine is None


@pytest.mark.asyncio
async def test_start_idempotent(engine_client: OmniVoiceEngineClient) -> None:
    """Test de start idempotente."""
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_get_engine.return_value = mock_engine
        await engine_client.start()
        await engine_client.start()  # Second call should be no-op
        mock_get_engine.assert_called_once()


@pytest.mark.asyncio
async def test_stop_when_not_started(engine_client: OmniVoiceEngineClient) -> None:
    """Test de stop cuando no está iniciado."""
    await engine_client.stop()  # Should not raise
    assert engine_client._started is False


@pytest.mark.asyncio
async def test_health(engine_client: OmniVoiceEngineClient) -> None:
    """Test de health check."""
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.health_check.return_value = {
            "model_loaded": True,
            "gpu_available": True,
            "device": "cuda:0",
            "stock_voices_count": 10,
        }
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        health = await engine_client.health()
        assert health.model_loaded is True
        assert health.gpu_available is True
        assert health.vram_free_mb == 0


@pytest.mark.asyncio
async def test_health_auto_starts(engine_client: OmniVoiceEngineClient) -> None:
    """Test de health auto-start si no iniciado."""
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.health_check.return_value = {"model_loaded": False, "gpu_available": False, "device": "cpu", "stock_voices_count": 0}
        mock_get_engine.return_value = mock_engine
        health = await engine_client.health()
        assert engine_client._started is True


@pytest.mark.asyncio
async def test_list_stock_voices(engine_client: OmniVoiceEngineClient) -> None:
    """Test de listado de voces stock."""
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.list_stock_voices.return_value = [
            {"voice_id": "es-mx-male", "language": "es", "gender": "male", "name": "Carlos"},
        ]
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        voices = await engine_client.list_stock_voices("es")
        assert len(voices) == 1
        assert voices[0].voice_id == "es-mx-male"
        assert voices[0].language == "es"


@pytest.mark.asyncio
async def test_list_stock_voices_auto_start(engine_client: OmniVoiceEngineClient) -> None:
    """Test de list_stock_voices auto-start."""
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.list_stock_voices.return_value = []
        mock_get_engine.return_value = mock_engine
        voices = await engine_client.list_stock_voices()
        assert engine_client._started is True


@pytest.mark.asyncio
async def test_list_emotions(engine_client: OmniVoiceEngineClient) -> None:
    """Test de listado de emociones."""
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.list_emotions.return_value = ["neutral", "happy"]
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        emotions = await engine_client.list_emotions()
        assert emotions == ["neutral", "happy"]


@pytest.mark.asyncio
async def test_synthesize_stock(engine_client: OmniVoiceEngineClient) -> None:
    """Test de síntesis con voz stock."""
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_stock.return_value = wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_stock(
            text="Hola",
            voice_id="es-mx-male",
            language="es",
        )
        assert isinstance(result, AudioResult)
        assert result.wav_bytes == wav
        assert result.sample_rate == 22050
        assert result.duration_sec > 0


@pytest.mark.asyncio
async def test_synthesize_stock_short_wav(engine_client: OmniVoiceEngineClient) -> None:
    """Test de síntesis con WAV muy corto (fallback parsing)."""
    short_wav = b"RIFF" + b"\x00" * 10  # Less than 44 bytes
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_stock.return_value = short_wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_stock(
            text="Hi",
            voice_id="es-mx-male",
            language="es",
        )
        assert result.sample_rate == 22050


@pytest.mark.asyncio
async def test_synthesize_stock_corrupt_wav(engine_client: OmniVoiceEngineClient) -> None:
    """Test de síntesis con WAV corrupto (exception in parsing)."""
    # WAV header that's 44+ bytes but has corrupt data
    corrupt_wav = b"RIFF" + b"\x00" * 100
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_stock.return_value = corrupt_wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_stock(
            text="Test",
            voice_id="es-mx-male",
            language="es",
        )
        assert isinstance(result, AudioResult)
        assert result.wav_bytes == corrupt_wav


@pytest.mark.asyncio
async def test_synthesize_clone(engine_client: OmniVoiceEngineClient) -> None:
    """Test de síntesis con voz clonada."""
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_clone.return_value = wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_clone(
            text="Hola",
            reference_audio_path="/path/to/ref.wav",
            language="es",
        )
        assert isinstance(result, AudioResult)
        assert result.wav_bytes == wav


@pytest.mark.asyncio
async def test_synthesize_clone_short_wav(engine_client: OmniVoiceEngineClient) -> None:
    """Test de síntesis clonada con WAV corto."""
    short_wav = b"RIFF" + b"\x00" * 10
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_clone.return_value = short_wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_clone(
            text="Hi",
            reference_audio_path="/path/to/ref.wav",
            language="es",
        )
        assert result.sample_rate == 22050


@pytest.mark.asyncio
async def test_synthesize_clone_corrupt_wav(engine_client: OmniVoiceEngineClient) -> None:
    """Test de síntesis clonada con WAV corrupto."""
    corrupt_wav = b"RIFF" + b"\x00" * 100
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_clone.return_value = corrupt_wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_clone(
            text="Test",
            reference_audio_path="/path/to/ref.wav",
            language="es",
        )
        assert isinstance(result, AudioResult)
        assert result.wav_bytes == corrupt_wav


@pytest.mark.asyncio
async def test_synthesize_stock_auto_start(engine_client: OmniVoiceEngineClient) -> None:
    """Test de synthesize_stock auto-start."""
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_stock.return_value = wav
        mock_get_engine.return_value = mock_engine
        result = await engine_client.synthesize_stock(text="Hi", voice_id="es-mx-male", language="es")
        assert engine_client._started is True


@pytest.mark.asyncio
async def test_synthesize_clone_auto_start(engine_client: OmniVoiceEngineClient) -> None:
    """Test de synthesize_clone auto-start."""
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_clone.return_value = wav
        mock_get_engine.return_value = mock_engine
        result = await engine_client.synthesize_clone(text="Hi", reference_audio_path="/ref.wav", language="es")
        assert engine_client._started is True
