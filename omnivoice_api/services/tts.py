"""Servicio de síntesis de texto a voz (TTS)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omnivoice_api.core.engine_client import AudioResult, OmniVoiceEngineClient
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.settings import get_settings


class TtsService:
    """Servicio de síntesis de voz."""

    def __init__(self, engine_client: OmniVoiceEngineClient | None = None) -> None:
        self._settings = get_settings()
        self._engine_client = engine_client

    async def _get_engine_client(self) -> OmniVoiceEngineClient:
        """Obtiene el cliente del engine (creándolo si es necesario)."""
        if self._engine_client is None:
            self._engine_client = OmniVoiceEngineClient()
            await self._engine_client.start()
        return self._engine_client

    async def synthesize_stock(
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> AudioResult:
        """Sintetiza texto con voz stock."""
        engine = await self._get_engine_client()

        # Validar voz stock
        stock_voices = await engine.list_stock_voices(language)
        if not any(v.voice_id == voice_id for v in stock_voices):
            raise VoiceNotFoundError(voice_id, "stock")

        # Validar idioma
        if language not in self._settings.OMNIVOICE_LANGUAGES:
            raise UnsupportedLanguageError(language, self._settings.OMNIVOICE_LANGUAGES)

        # Validar emoción
        emotions = await engine.list_emotions()
        if emotion and emotion not in emotions:
            raise UnsupportedEmotionError(emotion, emotions)

        # Sintetizar
        return await engine.synthesize_stock(
            text=text,
            voice_id=voice_id,
            language=language,
            speed=speed,
            emotion=emotion,
            intensity=intensity,
        )

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: Path,
        language: str,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> AudioResult:
        """Sintetiza texto con voz clonada (para Sprint 2)."""
        raise NotImplementedError("Clonado de voces se implementa en Sprint 2")

    async def close(self) -> None:
        """Cierra el cliente del engine."""
        if self._engine_client is not None:
            await self._engine_client.stop()
            self._engine_client = None
