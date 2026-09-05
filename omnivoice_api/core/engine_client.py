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


def _validate_wav_audio(wav_bytes: bytes) -> dict:
    """
    Valida un WAV y devuelve información detallada para debugging.
    
    Returns:
        Dict con: valid, sample_rate, duration_sec, num_channels, bits_per_sample, 
                  rms_amplitude, peak_amplitude, is_silent
    """
    result = {
        "valid": False,
        "sample_rate": 0,
        "duration_sec": 0.0,
        "num_channels": 0,
        "bits_per_sample": 0,
        "rms_amplitude": 0.0,
        "peak_amplitude": 0.0,
        "is_silent": True,
        "error": None
    }
    
    if len(wav_bytes) < 44:
        result["error"] = "WAV too small (< 44 bytes header)"
        return result
    
    try:
        # Parsear header WAV
        riff = wav_bytes[0:4]
        if riff != b'RIFF':
            result["error"] = f"Invalid RIFF header: {riff}"
            return result
            
        wave_fmt = wav_bytes[8:12]
        if wave_fmt != b'WAVE':
            result["error"] = f"Invalid WAVE format: {wave_fmt}"
            return result
        
        # Buscar chunk 'fmt '
        fmt_pos = wav_bytes.find(b'fmt ')
        if fmt_pos == -1:
            result["error"] = "fmt chunk not found"
            return result
            
        fmt_size = int.from_bytes(wav_bytes[fmt_pos+4:fmt_pos+8], byteorder='little')
        if fmt_size < 16:
            result["error"] = f"fmt chunk too small: {fmt_size}"
            return result
            
        audio_format = int.from_bytes(wav_bytes[fmt_pos+8:fmt_pos+10], byteorder='little')
        num_channels = int.from_bytes(wav_bytes[fmt_pos+10:fmt_pos+12], byteorder='little')
        sample_rate = int.from_bytes(wav_bytes[fmt_pos+12:fmt_pos+16], byteorder='little')
        byte_rate = int.from_bytes(wav_bytes[fmt_pos+16:fmt_pos+20], byteorder='little')
        block_align = int.from_bytes(wav_bytes[fmt_pos+20:fmt_pos+22], byteorder='little')
        bits_per_sample = int.from_bytes(wav_bytes[fmt_pos+22:fmt_pos+24], byteorder='little')
        
        # Buscar chunk 'data'
        data_pos = wav_bytes.find(b'data', fmt_pos + 8 + fmt_size)
        if data_pos == -1:
            result["error"] = "data chunk not found"
            return result
            
        data_size = int.from_bytes(wav_bytes[data_pos+4:data_pos+8], byteorder='little')
        audio_data = wav_bytes[data_pos+8:data_pos+8+data_size]
        
        if len(audio_data) != data_size:
            result["error"] = f"Data size mismatch: expected {data_size}, got {len(audio_data)}"
            return result
        
        # Calcular estadísticas de audio (asumiendo 16-bit PCM)
        if bits_per_sample == 16 and num_channels == 1:
            import struct
            num_samples = len(audio_data) // 2
            if num_samples > 0:
                # Desempaquetar muestras
                fmt_str = f'<{num_samples}h'
                samples = struct.unpack(fmt_str, audio_data)
                
                # RMS y peak
                sum_squares = sum(s * s for s in samples)
                rms = (sum_squares / num_samples) ** 0.5
                peak = max(abs(s) for s in samples)
                
                result["rms_amplitude"] = rms / 32767.0  # Normalizado 0-1
                result["peak_amplitude"] = peak / 32767.0
                result["is_silent"] = rms < 100  # Umbral arbitrario
        
        duration_sec = data_size / byte_rate if byte_rate > 0 else 0.0
        
        result.update({
            "valid": True,
            "sample_rate": sample_rate,
            "duration_sec": duration_sec,
            "num_channels": num_channels,
            "bits_per_sample": bits_per_sample,
        })
        
    except Exception as e:
        result["error"] = f"Parse error: {e}"
    
    return result


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

        log.info("engine_sending_to_omnivoice", text_preview=text[:100])
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
                error_type=type(e).__name__,
            )
            raise

        elapsed = time.perf_counter() - start_time
        
        # Validación detallada del audio generado
        validation = _validate_wav_audio(wav_bytes)
        sample_rate = validation["sample_rate"]
        duration_sec = validation["duration_sec"]
        
        log.info(
            "engine_generation_completed",
            elapsed_sec=elapsed,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            audio_bytes=len(wav_bytes),
            validation=validation,
        )
        
        # Log de advertencia si el audio parece silencioso
        if validation["is_silent"]:
            log.warning(
                "GENERATED AUDIO APPEARS SILENT",
                rms=validation["rms_amplitude"],
                peak=validation["peak_amplitude"],
                is_silent=validation["is_silent"],
            )
        else:
            log.info(
                "Audio validation OK",
                rms=validation["rms_amplitude"],
                peak=validation["peak_amplitude"],
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

        log.info("engine_sending_to_omnivoice", text_preview=text[:100])
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
                error_type=type(e).__name__,
            )
            raise

        elapsed = time.perf_counter() - start_time
        
        # Validación detallada del audio generado
        validation = _validate_wav_audio(wav_bytes)
        sample_rate = validation["sample_rate"]
        duration_sec = validation["duration_sec"]
        
        log.info(
            "engine_generation_completed",
            elapsed_sec=elapsed,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            audio_bytes=len(wav_bytes),
            validation=validation,
        )
        
        # Log de advertencia si el audio parece silencioso
        if validation["is_silent"]:
            log.warning(
                "GENERATED AUDIO APPEARS SILENT",
                rms=validation["rms_amplitude"],
                peak=validation["peak_amplitude"],
                is_silent=validation["is_silent"],
            )
        else:
            log.info(
                "Audio validation OK",
                rms=validation["rms_amplitude"],
                peak=validation["peak_amplitude"],
            )

        return AudioResult(
            wav_bytes=wav_bytes,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
        )
