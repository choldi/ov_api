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
from omnivoice_api.core.omnivoice_engine import GenerationParams
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedInstructError,
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
    return OmniVoiceEngineClient()


@pytest.mark.asyncio
async def test_start_and_stop(engine_client: OmniVoiceEngineClient) -> None:
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_get_engine.return_value = mock_engine
        await engine_client.start()
        assert engine_client._started is True
        assert engine_client._engine is mock_engine

        with patch("omnivoice_api.core.engine_client.close_engine", new_callable=AsyncMock):
            await engine_client.stop()
            assert engine_client._started is False


@pytest.mark.asyncio
async def test_synthesize_stock(engine_client: OmniVoiceEngineClient) -> None:
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_stock.return_value = wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_stock(
            text="Hola",
            voice_id="es-mx-male",
        )
        assert isinstance(result, AudioResult)
        assert result.wav_bytes == wav


@pytest.mark.asyncio
async def test_synthesize_stock_with_generation_params(engine_client: OmniVoiceEngineClient) -> None:
    wav = _make_wav_bytes()
    params = GenerationParams(num_step=16, denoise=False)
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_stock.return_value = wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_stock(
            text="Hola",
            voice_id="es-mx-male",
            generation_params=params,
        )
        assert isinstance(result, AudioResult)
        mock_engine.synthesize_stock.assert_called_once_with(
            text="Hola", voice_id="es-mx-male", speed=1.0, generation_params=params,
        )


@pytest.mark.asyncio
async def test_synthesize_instruct(engine_client: OmniVoiceEngineClient) -> None:
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_instruct.return_value = wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_instruct(
            text="Hello",
            instruct="female, british accent",
        )
        assert isinstance(result, AudioResult)
        assert result.wav_bytes == wav


@pytest.mark.asyncio
async def test_synthesize_clone_with_instruct(engine_client: OmniVoiceEngineClient) -> None:
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_clone.return_value = wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_clone(
            text="Hola",
            reference_audio_path="/path/to/ref.wav",
            instruct="male, portuguese accent",
        )
        assert isinstance(result, AudioResult)


@pytest.mark.asyncio
async def test_synthesize_clone_without_instruct(engine_client: OmniVoiceEngineClient) -> None:
    wav = _make_wav_bytes()
    with patch("omnivoice_api.core.engine_client.get_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = AsyncMock()
        mock_engine.synthesize_clone.return_value = wav
        mock_get_engine.return_value = mock_engine
        await engine_client.start()

        result = await engine_client.synthesize_clone(
            text="Hola",
            reference_audio_path="/path/to/ref.wav",
        )
        assert isinstance(result, AudioResult)


@pytest.mark.asyncio
async def test_health(engine_client: OmniVoiceEngineClient) -> None:
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
