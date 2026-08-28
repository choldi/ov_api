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
from omnivoice_api.repositories.voice_repository import VoiceRepository
from omnivoice_api.services.voice_service import VoiceService
from omnivoice_api.settings import get_settings


class TtsService:
    """Servicio de síntesis de voz."""

    def __init__(
        self,
        engine_client: OmniVoiceEngineClient | None = None,
        voice_service: VoiceService | None = None,
    ) -> None:
        self._settings = get_settings()
        self._engine_client = engine_client
        self._voice_service = voice_service

    async def _get_engine_client(self) -> OmniVoiceEngineClient:
        """Obtiene el cliente del engine (creándolo si es necesario)."""
        if self._engine_client is None:
            self._engine_client = OmniVoiceEngineClient()
            await self._engine_client.start()
        return self._engine_client

    async def _get_voice_service(self) -> VoiceService:
        """Obtiene el servicio de voces (creándolo si es necesario)."""
        if self._voice_service is None:
            self._voice_service = VoiceService()
            await self._voice_service.initialize()
        return self._voice_service

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
        """Sintetiza texto con voz (stock o clonada)."""
        # First check if this is a cloned voice
        try:
            voice_service = await self._get_voice_service()
            voice_data = await voice_service.get_voice(voice_id)
            # If we get here, it's a cloned voice
            return await self.synthesize_clone(
                text=text,
                voice_id=voice_id,
                language=language,
                speed=speed,
                emotion=emotion,
                intensity=intensity,
            )
        except VoiceNotFoundError:
            # Not a cloned voice, fall back to stock voice
            pass
        except Exception:
            # Other error (e.g., voice service not initialized), fall back to stock
            pass

        # If not a cloned voice, treat as stock voice
        engine = await self._get_engine_client()

        # Validar voz stock
        stock_voices = await engine.list_stock_voices(language)
        if not any(v.voice_id == voice_id for v in stock_voices):
            raise VoiceNotFoundError(voice_id, "stock")

        # Validar idioma
        if language not in self._settings.omnilang_list:
            raise UnsupportedLanguageError(language, self._settings.omnilang_list)

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
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> AudioResult:
        """Sintetiza texto con voz clonada."""
        # Get voice service
        voice_service = await self._get_voice_service()
        
        # Get voice data
        voice_data = await voice_service.get_voice(voice_id)
        
        # Extract reference audio path
        reference_audio_path = voice_data["reference_path"]
        
        # Validate language matches voice
        if voice_data["language"] != language:
            raise UnsupportedLanguageError(
                language, 
                [voice_data["language"]], 
                f"Voice {voice_id} is configured for language {voice_data['language']}"
            )
        
        # Get engine client
        engine = await self._get_engine_client()
        
        # Validate emotion (delegated to engine)
        # Note: We don't pre-validate emotions here because the engine might support
        # different emotions for cloned voices vs stock voices
        
        # Sintetizar con voz clonada
        return await engine.synthesize_clone(
            text=text,
            reference_audio_path=reference_audio_path,
            language=language,
            emotion=emotion,
            intensity=intensity,
        )

    async def close(self) -> None:
        """Cierra el cliente del engine."""
        if self._engine_client is not None:
            await self._engine_client.stop()
            self._engine_client = None
