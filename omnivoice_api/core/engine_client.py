"""Cliente para interactuar con el motor OmniVoice."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import structlog

from omnivoice_api.core.omnivoice_engine import OmniVoiceEngine, get_engine, close_engine
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)

logger = structlog.get_logger(__name__)


@dataclass
class StockVoice:
    """Voz stock disponible en el motor."""
    voice_id: str
    language: str
    gender: str
    name: str


@dataclass
class AudioResult:
    """Resultado de la síntesis de audio."""
    wav_bytes: bytes
    duration_sec: float
    sample_rate: int


@dataclass
class EngineHealth:
    """Estado de salud del motor."""
    reachable: bool
    model_loaded: bool
    gpu_available: bool
    vram_free_mb: int


def _parse_wav_header(wav_bytes: bytes) -> tuple[int, float]:
    """Parsea la cabecera de un WAV y devuelve (sample_rate, duration_sec).

    Si la cabecera no es válida, devuelve valores por defecto.
    """
    sample_rate = 22050
    duration_sec = 0.0
    if len(wav_bytes) >= 44:
        try:
            sample_rate = int.from_bytes(wav_bytes[24:28], byteorder='little')
            byte_rate = int.from_bytes(wav_bytes[28:32], byteorder='little')
            subchunk2_size = int.from_bytes(wav_bytes[40:44], byteorder='little')
            duration_sec = subchunk2_size / byte_rate if byte_rate > 0 else 0.0
        except Exception:
            duration_sec = len(wav_bytes) / (sample_rate * 2)
    else:
        duration_sec = len(wav_bytes) / (sample_rate * 2)
    return sample_rate, duration_sec


class OmniVoiceEngineClient:
    """Cliente de alto nivel para el motor OmniVoice usado por los servicios."""

    def __init__(self) -> None:
        self._engine: OmniVoiceEngine | None = None
        self._started = False

    async def start(self) -> None:
        """Inicializa el cliente y el motor subyacente."""
        if not self._started:
            logger.info("engine_client_starting")
            self._engine = await get_engine()
            self._started = True
            logger.info("engine_client_started")

    async def stop(self) -> None:
        """Detiene el cliente y libera recursos."""
        if self._started:
            logger.info("engine_client_stopping")
            await close_engine()
            self._engine = None
            self._started = False
            logger.info("engine_client_stopped")

    async def health(self) -> EngineHealth:
        """Obtiene el estado de salud del motor."""
        if not self._started:
            await self.start()
        assert self._engine is not None
        log = logger.bind()
        log.info("engine_health_check_start")
        health_dict = await self._engine.health_check()
        result = EngineHealth(
            reachable=health_dict.get("model_loaded", False),
            model_loaded=health_dict.get("model_loaded", False),
            gpu_available=health_dict.get("gpu_available", False),
            vram_free_mb=health_dict.get("vram_free_mb", 0),
        )
        log.info(
            "engine_health_check_completed",
            reachable=result.reachable,
            model_loaded=result.model_loaded,
            gpu_available=result.gpu_available,
            vram_free_mb=result.vram_free_mb,
        )
        return result

    async def list_stock_voices(self, language: str | None = None) -> list[StockVoice]:
        """Lista voces stock disponibles."""
        if not self._started:
            await self.start()
        assert self._engine is not None
        log = logger.bind(language=language)
        log.info("engine_list_stock_voices_start")
        voices_dicts = await self._engine.list_stock_voices(language=language)
        voices = [
            StockVoice(
                voice_id=v["voice_id"],
                language=v["language"],
                gender=v["gender"],
                name=v["name"],
            )
            for v in voices_dicts
        ]
        log.info("engine_list_stock_voices_completed", count=len(voices))
        return voices

    async def list_emotions(self) -> list[str]:
        """Lista emociones soportadas."""
        if not self._started:
            await self.start()
        assert self._engine is not None
        log = logger.bind()
        log.info("engine_list_emotions_start")
        emotions = await self._engine.list_emotions()
        log.info("engine_list_emotions_completed", count=len(emotions), emotions=emotions)
        return emotions

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
        if not self._started:
            await self.start()
        assert self._engine is not None

        call_id = str(uuid.uuid4())
        log = logger.bind(
            call_id=call_id,
            operation="synthesize_stock",
            voice_id=voice_id,
            language=language,
            text_length=len(text),
            speed=speed,
            emotion=emotion,
            intensity=intensity,
        )

        log.info("engine_sending_to_omnivoice")
        start_time = time.perf_counter()

        try:
            wav_bytes = await self._engine.synthesize_stock(
                text=text,
                voice_id=voice_id,
                language=language,
                speed=speed,
                emotion=emotion,
                intensity=intensity,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            log.error(
                "engine_generation_failed",
                elapsed_sec=elapsed,
                error=str(e),
            )
            raise

        elapsed = time.perf_counter() - start_time
        sample_rate, duration_sec = _parse_wav_header(wav_bytes)

        log.info(
            "engine_generation_completed",
            elapsed_sec=elapsed,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            audio_bytes=len(wav_bytes),
        )

        return AudioResult(
            wav_bytes=wav_bytes,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
        )

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: str,
        language: str,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> AudioResult:
        """Sintetiza texto con voz clonada."""
        if not self._started:
            await self.start()
        assert self._engine is not None

        call_id = str(uuid.uuid4())
        log = logger.bind(
            call_id=call_id,
            operation="synthesize_clone",
            reference_audio_path=reference_audio_path,
            language=language,
            text_length=len(text),
            emotion=emotion,
            intensity=intensity,
        )

        log.info("engine_sending_to_omnivoice")
        start_time = time.perf_counter()

        try:
            wav_bytes = await self._engine.synthesize_clone(
                text=text,
                reference_audio_path=reference_audio_path,
                language=language,
                emotion=emotion,
                intensity=intensity,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            log.error(
                "engine_generation_failed",
                elapsed_sec=elapsed,
                error=str(e),
            )
            raise

        elapsed = time.perf_counter() - start_time
        sample_rate, duration_sec = _parse_wav_header(wav_bytes)

        log.info(
            "engine_generation_completed",
            elapsed_sec=elapsed,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            audio_bytes=len(wav_bytes),
        )

        return AudioResult(
            wav_bytes=wav_bytes,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
        )
