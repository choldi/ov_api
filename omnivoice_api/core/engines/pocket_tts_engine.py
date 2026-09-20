"""Pocket TTS engine (Kyutai) — CPU-first with voice cloning."""

from __future__ import annotations

import asyncio
import io
import logging
import struct
import wave
from typing import Any

from omnivoice_api.core.engine_base import EngineCapabilities, TtsEngineBase
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    FeatureNotSupportedError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.settings import get_settings

logger = logging.getLogger(__name__)

# Pocket TTS preset voice names
_POCKET_VOICE_PRESETS: dict[str, str] = {
    "alba": "alba",
    "anna": "anna",
    "giovanni": "giovanni",
    "lola": "lola",
}

# Mapping from our voice_id scheme to Pocket TTS voice presets
_STOCK_VOICE_MAP: dict[str, dict[str, str]] = {
    "es-mx-male": {"preset": "giovanni", "language": "es", "gender": "male", "name": "Spanish MX Male"},
    "es-mx-female": {"preset": "lola", "language": "es", "gender": "female", "name": "Spanish MX Female"},
    "es-es-male": {"preset": "giovanni", "language": "es", "gender": "male", "name": "Spanish Spain Male"},
    "es-es-female": {"preset": "lola", "language": "es", "gender": "female", "name": "Spanish Spain Female"},
    "en-us-male": {"preset": "giovanni", "language": "en", "gender": "male", "name": "English US Male"},
    "en-us-female": {"preset": "anna", "language": "en", "gender": "female", "name": "English US Female"},
    "en-gb-male": {"preset": "giovanni", "language": "en", "gender": "male", "name": "English UK Male"},
    "en-gb-female": {"preset": "alba", "language": "en", "gender": "female", "name": "English UK Female"},
    "fr-fr-male": {"preset": "giovanni", "language": "fr", "gender": "male", "name": "French Male"},
    "fr-fr-female": {"preset": "alba", "language": "fr", "gender": "female", "name": "French Female"},
}

# Languages Pocket TTS supports
_POCKET_LANGUAGES = {"en", "es", "fr", "de", "it", "pt"}


class PocketTTSEngine(TtsEngineBase):
    """Pocket TTS engine — CPU-first, supports voice cloning from audio prompts."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model: Any = None
        self._voice_states: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "pocket_tts"

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            stock_voices=True,
            voice_cloning=True,
            instruct_voice_design=False,
            emotions=False,
            streaming=False,
            supported_languages=list(_POCKET_LANGUAGES),
        )

    async def initialize(self) -> None:
        if self._model is not None:
            return
        try:
            from pocket_tts import TTSModel

            logger.info("Initializing Pocket TTS engine (model=%s)...", self._settings.POCKET_TTS_MODEL)
            self._model = await asyncio.to_thread(TTSModel.load_model)
            # Pre-load voice states for stock presets
            for preset_name in _POCKET_VOICE_PRESETS:
                try:
                    state = await asyncio.to_thread(
                        self._model.get_state_for_audio_prompt, preset_name
                    )
                    self._voice_states[preset_name] = state
                except Exception as e:
                    logger.warning("Could not load voice preset '%s': %s", preset_name, e)
            logger.info("Pocket TTS engine initialized")
        except ImportError:
            raise EngineUnavailableError(
                "pocket-tts no está instalado. Ejecuta: pip install pocket-tts"
            )
        except Exception as e:
            raise EngineUnavailableError(f"Error inicializando Pocket TTS: {e}")

    async def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
    ) -> bytes:
        voice = _STOCK_VOICE_MAP.get(voice_id)
        if not voice:
            valid_ids = list(_STOCK_VOICE_MAP.keys())
            err = VoiceNotFoundError(voice_id, "stock")
            err.valid_voice_ids = valid_ids
            raise err

        if language not in _POCKET_LANGUAGES:
            raise UnsupportedLanguageError(language, list(_POCKET_LANGUAGES))

        preset = voice["preset"]
        state = self._voice_states.get(preset)
        if state is None:
            raise EngineUnavailableError(f"Voice preset '{preset}' no cargado")

        try:
            audio = await asyncio.to_thread(
                self._model.generate_audio, state, text
            )
            return self._tensor_to_wav(audio)
        except Exception as e:
            raise EngineUnavailableError(f"Error sintetizando con Pocket TTS: {e}")

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: str,
        language: str,
        speed: float = 1.0,
        ref_text: str | None = None,
    ) -> bytes:
        import os

        if not os.path.exists(reference_audio_path):
            raise EngineUnavailableError(f"Reference audio no encontrado: {reference_audio_path}")

        try:
            state = await asyncio.to_thread(
                self._model.get_state_for_audio_prompt, reference_audio_path
            )
            audio = await asyncio.to_thread(
                self._model.generate_audio, state, text
            )
            return self._tensor_to_wav(audio)
        except Exception as e:
            raise EngineUnavailableError(f"Error clonando voz con Pocket TTS: {e}")

    async def synthesize_instruct(
        self,
        *,
        text: str,
        instruct: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
    ) -> bytes:
        raise FeatureNotSupportedError("instruct/voice design", self.name)

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        voices = [
            {"voice_id": vid, "language": v["language"], "gender": v["gender"], "name": v["name"]}
            for vid, v in _STOCK_VOICE_MAP.items()
        ]
        if language:
            voices = [v for v in voices if v["language"] == language]
        return voices

    async def health_check(self) -> dict:
        return {
            "model_loaded": self._model is not None,
            "gpu_available": False,
            "device": "cpu",
            "stock_voices_count": len(_STOCK_VOICE_MAP),
            "vram_free_mb": 0,
            "mode": "REAL" if self._model else "NOT_LOADED",
            "engine": self.name,
        }

    def _tensor_to_wav(self, audio: Any) -> bytes:
        """Convert tensor/numpy output from Pocket TTS to WAV bytes."""
        import numpy as np

        if hasattr(audio, "numpy"):
            audio = audio.numpy()
        audio = np.asarray(audio, dtype=np.float32)

        if audio.ndim > 1:
            audio = audio.flatten()

        sample_rate = getattr(self._model, "sample_rate", 24000)
        audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        return buffer.getvalue()
