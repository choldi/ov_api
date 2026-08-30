"""Tests unitarios para el motor OmniVoice."""

from __future__ import annotations

from unittest.mock import patch, AsyncMock

import pytest

from omnivoice_api.core.omnivoice_engine import (
    OmniVoiceEngine,
    get_engine,
    close_engine,
)
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)


@pytest.fixture(autouse=True)
def reset_engine():
    """Resetea el singleton del engine entre tests."""
    OmniVoiceEngine._instance = None
    OmniVoiceEngine._initialized = False
    import omnivoice_api.core.omnivoice_engine as mod
    mod._engine_instance = None
    yield
    OmniVoiceEngine._instance = None
    OmniVoiceEngine._initialized = False
    mod._engine_instance = None


@pytest.fixture
def engine() -> OmniVoiceEngine:
    """Engine para tests (ya inicializado)."""
    e = OmniVoiceEngine()
    e._model = object()  # Mock model
    e._stock_voices = e._get_mock_stock_voices()
    return e


@pytest.mark.asyncio
async def test_engine_singleton():
    """Test de que el engine es singleton."""
    e1 = OmniVoiceEngine()
    e2 = OmniVoiceEngine()
    assert e1 is e2


@pytest.mark.asyncio
async def test_engine_initialize(engine: OmniVoiceEngine) -> None:
    """Test de inicialización del engine."""
    assert engine._model is not None
    assert len(engine._stock_voices) > 0


@pytest.mark.asyncio
async def test_engine_initialize_already_initialized(engine: OmniVoiceEngine) -> None:
    """Test de inicialización idempotente."""
    engine._model = object()
    await engine.initialize()  # Should not reinitialize
    assert engine._model is not None


@pytest.mark.asyncio
async def test_engine_warmup(engine: OmniVoiceEngine) -> None:
    """Test de warmup."""
    await engine.warmup()  # Should not raise


@pytest.mark.asyncio
async def test_engine_synthesize_stock_success(engine: OmniVoiceEngine) -> None:
    """Test de síntesis stock exitosa."""
    wav = await engine.synthesize_stock(
        text="Hola",
        voice_id="es-mx-male",
        language="es",
    )
    assert isinstance(wav, bytes)
    assert len(wav) > 0


@pytest.mark.asyncio
async def test_engine_synthesize_stock_voice_not_found(engine: OmniVoiceEngine) -> None:
    """Test de síntesis stock con voz no encontrada."""
    with pytest.raises(VoiceNotFoundError):
        await engine.synthesize_stock(
            text="Hola",
            voice_id="nonexistent",
            language="es",
        )


@pytest.mark.asyncio
async def test_engine_synthesize_stock_unsupported_language(engine: OmniVoiceEngine) -> None:
    """Test de síntesis stock con idioma no soportado."""
    with pytest.raises(UnsupportedLanguageError):
        await engine.synthesize_stock(
            text="Hola",
            voice_id="es-mx-male",
            language="xx",
        )


@pytest.mark.asyncio
async def test_engine_synthesize_stock_unsupported_emotion(engine: OmniVoiceEngine) -> None:
    """Test de síntesis stock con emoción no soportada."""
    with pytest.raises(UnsupportedEmotionError):
        await engine.synthesize_stock(
            text="Hola",
            voice_id="es-mx-male",
            language="es",
            emotion="invalid-emotion",
        )


@pytest.mark.asyncio
async def test_engine_synthesize_stock_with_emotion(engine: OmniVoiceEngine) -> None:
    """Test de síntesis stock con emoción válida."""
    wav = await engine.synthesize_stock(
        text="Hola",
        voice_id="es-mx-male",
        language="es",
        emotion="happy",
    )
    assert isinstance(wav, bytes)


@pytest.mark.asyncio
async def test_engine_synthesize_clone(engine: OmniVoiceEngine) -> None:
    """Test de síntesis con voz clonada."""
    wav = await engine.synthesize_clone(
        text="Hola",
        reference_audio_path="/tmp/ref.wav",
        language="es",
    )
    assert isinstance(wav, bytes)


@pytest.mark.asyncio
async def test_engine_synthesize_clone_unsupported_language(engine: OmniVoiceEngine) -> None:
    """Test de síntesis clonada con idioma no soportado."""
    with pytest.raises(UnsupportedLanguageError):
        await engine.synthesize_clone(
            text="Hola",
            reference_audio_path="/tmp/ref.wav",
            language="xx",
        )


@pytest.mark.asyncio
async def test_engine_synthesize_clone_unsupported_emotion(engine: OmniVoiceEngine) -> None:
    """Test de síntesis clonada con emoción no soportada."""
    with pytest.raises(UnsupportedEmotionError):
        await engine.synthesize_clone(
            text="Hola",
            reference_audio_path="/tmp/ref.wav",
            language="es",
            emotion="invalid",
        )


@pytest.mark.asyncio
async def test_engine_list_stock_voices(engine: OmniVoiceEngine) -> None:
    """Test de listado de voces stock."""
    voices = await engine.list_stock_voices()
    assert len(voices) == 22


@pytest.mark.asyncio
async def test_engine_list_stock_voices_filtered(engine: OmniVoiceEngine) -> None:
    """Test de listado de voces stock filtradas."""
    voices = await engine.list_stock_voices(language="es")
    assert all(v["language"] == "es" for v in voices)


@pytest.mark.asyncio
async def test_engine_list_emotions(engine: OmniVoiceEngine) -> None:
    """Test de listado de emociones."""
    emotions = await engine.list_emotions()
    assert "neutral" in emotions
    assert "happy" in emotions


@pytest.mark.asyncio
async def test_engine_health_check(engine: OmniVoiceEngine) -> None:
    """Test de health check."""
    health = await engine.health_check()
    assert health["model_loaded"] is True
    assert "gpu_available" in health


@pytest.mark.asyncio
async def test_engine_generate_mock_wav(engine: OmniVoiceEngine) -> None:
    """Test de generación de WAV mock."""
    wav = engine._generate_mock_wav(duration_sec=1.0, sample_rate=22050)
    assert isinstance(wav, bytes)
    assert len(wav) > 44  # At least header


@pytest.mark.asyncio
async def test_get_engine_singleton() -> None:
    """Test de get_engine retorna singleton."""
    e1 = await get_engine()
    e2 = await get_engine()
    assert e1 is e2


@pytest.mark.asyncio
async def test_close_engine() -> None:
    """Test de close_engine."""
    await get_engine()
    await close_engine()
    import omnivoice_api.core.omnivoice_engine as mod
    assert mod._engine_instance is None


@pytest.mark.asyncio
async def test_close_engine_when_none() -> None:
    """Test de close_engine cuando no hay engine."""
    await close_engine()  # Should not raise


@pytest.mark.asyncio
async def test_engine_synthesize_clone_missing_reference(engine: OmniVoiceEngine) -> None:
    """Test de síntesis clonada con audio de referencia faltante (usa mock)."""
    wav = await engine.synthesize_clone(
        text="Test",
        reference_audio_path="/nonexistent/path.wav",
        language="es",
    )
    assert isinstance(wav, bytes)
