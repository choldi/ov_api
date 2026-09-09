"""Tests unitarios para el motor OmniVoice."""

from __future__ import annotations

from unittest.mock import patch, AsyncMock

import pytest

from omnivoice_api.core.omnivoice_engine import (
    OmniVoiceEngine,
    GenerationParams,
    VALID_INSTRUCT_TOKENS_EN,
    STOCK_VOICE_INSTRUCTS,
    _validate_instruct,
    get_engine,
    close_engine,
)
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedInstructError,
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
    e._model = object()
    e._stock_voices = e._get_mock_stock_voices()
    return e


@pytest.mark.asyncio
async def test_engine_singleton():
    e1 = OmniVoiceEngine()
    e2 = OmniVoiceEngine()
    assert e1 is e2


@pytest.mark.asyncio
async def test_engine_initialize(engine: OmniVoiceEngine) -> None:
    assert engine._model is not None
    assert len(engine._stock_voices) > 0


@pytest.mark.asyncio
async def test_engine_warmup(engine: OmniVoiceEngine) -> None:
    await engine.warmup()


@pytest.mark.asyncio
async def test_engine_synthesize_stock_success(engine: OmniVoiceEngine) -> None:
    wav = await engine.synthesize_stock(
        text="Hola",
        voice_id="es-mx-male",
    )
    assert isinstance(wav, bytes)
    assert len(wav) > 0


@pytest.mark.asyncio
async def test_engine_synthesize_stock_voice_not_found(engine: OmniVoiceEngine) -> None:
    with pytest.raises(VoiceNotFoundError):
        await engine.synthesize_stock(text="Hola", voice_id="nonexistent")


@pytest.mark.asyncio
async def test_engine_synthesize_stock_with_generation_params(engine: OmniVoiceEngine) -> None:
    params = GenerationParams(num_step=16, denoise=False, guidance_scale=3.0)
    wav = await engine.synthesize_stock(
        text="Hola",
        voice_id="es-mx-male",
        generation_params=params,
    )
    assert isinstance(wav, bytes)


@pytest.mark.asyncio
async def test_engine_synthesize_instruct(engine: OmniVoiceEngine) -> None:
    wav = await engine.synthesize_instruct(
        text="Hello",
        instruct="female, young adult, british accent",
    )
    assert isinstance(wav, bytes)


@pytest.mark.asyncio
async def test_engine_synthesize_instruct_invalid(engine: OmniVoiceEngine) -> None:
    with pytest.raises(UnsupportedInstructError):
        await engine.synthesize_instruct(
            text="Hello",
            instruct="Mexican Spanish accent",
        )


@pytest.mark.asyncio
async def test_engine_synthesize_clone(engine: OmniVoiceEngine) -> None:
    wav = await engine.synthesize_clone(
        text="Hola",
        reference_audio_path="/tmp/ref.wav",
    )
    assert isinstance(wav, bytes)


@pytest.mark.asyncio
async def test_engine_synthesize_clone_with_instruct(engine: OmniVoiceEngine) -> None:
    wav = await engine.synthesize_clone(
        text="Hola",
        reference_audio_path="/tmp/ref.wav",
        instruct="male, portuguese accent",
    )
    assert isinstance(wav, bytes)


@pytest.mark.asyncio
async def test_engine_list_stock_voices(engine: OmniVoiceEngine) -> None:
    voices = await engine.list_stock_voices()
    assert len(voices) == 22


@pytest.mark.asyncio
async def test_engine_list_stock_voices_filtered(engine: OmniVoiceEngine) -> None:
    voices = await engine.list_stock_voices(language="es")
    assert all(v["language"] == "es" for v in voices)


@pytest.mark.asyncio
async def test_engine_health_check(engine: OmniVoiceEngine) -> None:
    health = await engine.health_check()
    assert health["model_loaded"] is True
    assert "gpu_available" in health


@pytest.mark.asyncio
async def test_engine_generate_mock_wav(engine: OmniVoiceEngine) -> None:
    wav = engine._generate_test_tone_wav(duration_sec=1.0, sample_rate=22050)
    assert isinstance(wav, bytes)
    assert len(wav) > 44


# --- Validación de instructs ---

def test_validate_instruct_valid():
    _validate_instruct("male, british accent")


def test_validate_instruct_single_token():
    _validate_instruct("female")


def test_validate_instruct_invalid():
    with pytest.raises(UnsupportedInstructError):
        _validate_instruct("Mexican Spanish accent")


def test_validate_instruct_mixed_valid_invalid():
    with pytest.raises(UnsupportedInstructError):
        _validate_instruct("male, Mexican Spanish accent")


def test_all_stock_voice_instructs_are_valid():
    """Todos los instructs de STOCK_VOICE_INSTRUCTS deben contener solo tokens válidos."""
    for voice_id, instruct in STOCK_VOICE_INSTRUCTS.items():
        _validate_instruct(instruct)  # Should not raise


def test_valid_tokens_complete():
    assert "male" in VALID_INSTRUCT_TOKENS_EN
    assert "female" in VALID_INSTRUCT_TOKENS_EN
    assert "child" in VALID_INSTRUCT_TOKENS_EN
    assert "elderly" in VALID_INSTRUCT_TOKENS_EN
    assert "british accent" in VALID_INSTRUCT_TOKENS_EN
    assert "whisper" in VALID_INSTRUCT_TOKENS_EN


# --- GenerationParams ---

def test_generation_params_defaults():
    p = GenerationParams()
    assert p.num_step == 32
    assert p.denoise is True
    assert p.guidance_scale == 2.0
    assert p.duration is None


def test_generation_params_to_kwargs():
    p = GenerationParams(num_step=16, duration=5.0)
    kw = p.to_kwargs()
    assert kw["num_step"] == 16
    assert kw["duration"] == 5.0
    assert kw["denoise"] is True


@pytest.mark.asyncio
async def test_get_engine_singleton() -> None:
    e1 = await get_engine()
    e2 = await get_engine()
    assert e1 is e2


@pytest.mark.asyncio
async def test_close_engine() -> None:
    await get_engine()
    await close_engine()
    import omnivoice_api.core.omnivoice_engine as mod
    assert mod._engine_instance is None


@pytest.mark.asyncio
async def test_close_engine_when_none() -> None:
    await close_engine()
