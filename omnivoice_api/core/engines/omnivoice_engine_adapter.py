"""Adapter wrapping the legacy OmniVoiceEngine into the TtsEngineBase interface."""

from __future__ import annotations

import logging

from omnivoice_api.core.engine_base import EngineCapabilities, TtsEngineBase
from omnivoice_api.core.omnivoice_engine import (
    OmniVoiceEngine,
    get_engine,
)

logger = logging.getLogger(__name__)


class OmniVoiceAdapter(TtsEngineBase):
    """Wraps the existing OmniVoiceEngine singleton into the new TtsEngineBase ABC."""

    def __init__(self) -> None:
        self._engine: OmniVoiceEngine | None = None

    @property
    def name(self) -> str:
        return "omnivoice"

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            stock_voices=True,
            voice_cloning=True,
            instruct_voice_design=True,
            emotions=True,
            streaming=False,
            supported_languages=["es", "en", "fr", "de", "it", "pt", "zh", "ja", "ko"],
        )

    async def initialize(self) -> None:
        self._engine = await get_engine()

    async def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
    ) -> bytes:
        assert self._engine is not None
        return await self._engine.synthesize_stock(
            text=text,
            voice_id=voice_id,
            speed=speed,
            emotion=emotion,
            language=language,
        )

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: str,
        language: str,
        speed: float = 1.0,
        ref_text: str | None = None,
    ) -> bytes:
        assert self._engine is not None
        return await self._engine.synthesize_clone(
            text=text,
            reference_audio_path=reference_audio_path,
            ref_text=ref_text,
            speed=speed,
            language=language,
        )

    async def synthesize_instruct(
        self,
        *,
        text: str,
        instruct: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
    ) -> bytes:
        assert self._engine is not None
        return await self._engine.synthesize_instruct(
            text=text,
            instruct=instruct,
            speed=speed,
            emotion=emotion,
            language=language,
        )

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        assert self._engine is not None
        return await self._engine.list_stock_voices(language=language)

    async def health_check(self) -> dict:
        assert self._engine is not None
        return await self._engine.health_check()

    async def warmup(self) -> None:
        if self._engine is not None:
            await self._engine.warmup()

    async def close(self) -> None:
        from omnivoice_api.core.omnivoice_engine import close_engine

        await close_engine()
        self._engine = None
