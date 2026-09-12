"""Servicio de síntesis de texto a voz (TTS)."""

from __future__ import annotations

from omnivoice_api.core.engine_client import AudioResult, OmniVoiceEngineClient
from omnivoice_api.core.omnivoice_engine import GenerationParams
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
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
        if self._engine_client is None:
            self._engine_client = OmniVoiceEngineClient()
            await self._engine_client.start()
        return self._engine_client

    async def _get_voice_service(self) -> VoiceService:
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
        generation_params: GenerationParams | None = None,
    ) -> AudioResult:
        """Sintetiza texto con voz stock."""
        try:
            voice_service = await self._get_voice_service()
            voice_data = await voice_service.get_voice(voice_id)
            return await self.synthesize_clone(
                text=text,
                voice_id=voice_id,
                language=language,
                speed=speed,
                emotion=emotion,
                generation_params=generation_params,
            )
        except VoiceNotFoundError:
            pass
        except Exception:
            pass

        engine = await self._get_engine_client()

        stock_voices = await engine.list_stock_voices(language)
        if not any(v.voice_id == voice_id for v in stock_voices):
            valid_ids = [v.voice_id for v in stock_voices]
            err = VoiceNotFoundError(voice_id, "stock")
            err.valid_voice_ids = valid_ids
            raise err

        if language not in self._settings.omnilang_list:
            raise UnsupportedLanguageError(language, self._settings.omnilang_list)

        return await engine.synthesize_stock(
            text=text,
            voice_id=voice_id,
            speed=speed,
            emotion=emotion,
            generation_params=generation_params,
        )

    async def synthesize_instruct(
        self,
        *,
        text: str,
        instruct: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
        generation_params: GenerationParams | None = None,
    ) -> AudioResult:
        """Sintetiza texto con instruct personalizado (voice design libre)."""
        engine = await self._get_engine_client()

        if language not in self._settings.omnilang_list:
            raise UnsupportedLanguageError(language, self._settings.omnilang_list)

        return await engine.synthesize_instruct(
            text=text,
            instruct=instruct,
            speed=speed,
            emotion=emotion,
            generation_params=generation_params,
        )

    async def synthesize_clone(
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        instruct: str | None = None,
        emotion: str | None = None,
        generation_params: GenerationParams | None = None,
    ) -> AudioResult:
        """Sintetiza texto con voz clonada."""
        voice_service = await self._get_voice_service()
        voice_data = await voice_service.get_voice(voice_id)
        reference_audio_path = voice_data["reference_path"]

        if voice_data["language"] != language:
            raise UnsupportedLanguageError(language, [voice_data["language"]])

        engine = await self._get_engine_client()

        return await engine.synthesize_clone(
            text=text,
            reference_audio_path=reference_audio_path,
            instruct=instruct,
            speed=speed,
            emotion=emotion,
            generation_params=generation_params,
        )

    async def close(self) -> None:
        if self._engine_client is not None:
            await self._engine_client.stop()
            self._engine_client = None
