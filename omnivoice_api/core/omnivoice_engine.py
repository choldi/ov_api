"""Interfaz y implementación del motor OmniVoice."""

from __future__ import annotations

import asyncio
import io
import logging
import math
import struct
import wave
from pathlib import Path
from typing import Protocol

import torch

from omnivoice_api.settings import get_settings
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    VoiceNotFoundError,
)

logger = logging.getLogger(__name__)


class OmniVoiceEngineInterface(Protocol):
    """Protocolo para el motor de síntesis."""

    async def synthesize_stock(
        self,
        *,
        text: str,
        voice_id: str,
        language: str | None = None,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        ...

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: str,
        language: str | None = None,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        ...

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        ...

    async def list_emotions(self) -> list[str]:
        ...

    async def health_check(self) -> dict:
        ...

    async def warmup(self) -> None:
        ...


# Mapeo de voces stock a instrucciones de voz design
STOCK_VOICE_INSTRUCTS: dict[str, str] = {
    "es-mx-male": "male voice, Mexican Spanish accent",
    "es-mx-female": "female voice, Mexican Spanish accent",
    "es-es-male": "male voice, Spanish Spain accent",
    "es-es-female": "female voice, Spanish Spain accent",
    "en-us-male": "male voice, American English accent",
    "en-us-female": "female voice, American English accent",
    "en-gb-male": "male voice, British English accent",
    "en-gb-female": "female voice, British English accent",
    "fr-fr-male": "male voice, French accent",
    "fr-fr-female": "female voice, French accent",
    "de-de-male": "male voice, German accent",
    "de-de-female": "female voice, German accent",
    "it-it-male": "male voice, Italian accent",
    "it-it-female": "female voice, Italian accent",
    "pt-br-male": "male voice, Brazilian Portuguese accent",
    "pt-br-female": "female voice, Brazilian Portuguese accent",
    "zh-cn-male": "male voice, Mandarin Chinese accent",
    "zh-cn-female": "female voice, Mandarin Chinese accent",
    "ja-jp-male": "male voice, Japanese accent",
    "ja-jp-female": "female voice, Japanese accent",
    "ko-kr-male": "male voice, Korean accent",
    "ko-kr-female": "female voice, Korean accent",
}


def _get_dtype() -> torch.dtype:
    """Convierte el string de dtype a torch.dtype."""
    settings = get_settings()
    dtype_map = {
        "float16": torch.float16,
        "float32": torch.float32,
        "int8": torch.int8,
    }
    return dtype_map.get(settings.OMNIVOICE_DTYPE, torch.float16)


class OmniVoiceEngine:
    """
    Implementación del motor OmniVoice usando la API de Python directamente.
    
    Si OMNIVOICE_USE_MOCK=True, genera tonos de prueba.
    Si OMNIVOICE_USE_MOCK=False, usa OmniVoice.from_pretrained().
    """

    _instance: OmniVoiceEngine | None = None
    _initialized: bool = False

    def __new__(cls) -> OmniVoiceEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._settings = get_settings()
        self._model = None
        self._stock_voices: list[dict] = []
        self._emotions: list[str] = ["neutral", "happy", "sad", "angry", "surprised"]
        self._use_mock: bool = self._settings.OMNIVOICE_USE_MOCK

    async def initialize(self) -> None:
        """Inicializa el modelo."""
        if self._model is not None:
            return

        logger.info("Initializing OmniVoice engine...")
        self._settings = get_settings()
        self._use_mock = self._settings.OMNIVOICE_USE_MOCK
        logger.info("OMNIVOICE_USE_MOCK=%s", self._use_mock)

        if self._use_mock:
            logger.warning("MODO MOCK: generando tonos de prueba")
            self._stock_voices = self._get_mock_stock_voices()
            await self.warmup()
            logger.info("Mock engine inicializado")
            return

        # Modo REAL: cargar modelo OmniVoice
        logger.info("Modo REAL: cargando OmniVoice...")
        
        try:
            from omnivoice import OmniVoice
            
            self._model = OmniVoice.from_pretrained(
                self._settings.OMNIVOICE_MODEL_ID,
                device_map=self._settings.OMNIVOICE_DEVICE,
                dtype=_get_dtype(),
            )
            self._stock_voices = self._get_mock_stock_voices()
            await self.warmup()
            logger.info("Engine OmniVoice REAL inicializado")
        except Exception as e:
            logger.error("Error cargando OmniVoice: %s", e)
            raise EngineUnavailableError(f"No se pudo cargar el modelo OmniVoice: {e}")

    async def warmup(self) -> None:
        """Verifica que el modelo responde."""
        if self._use_mock:
            await asyncio.sleep(0.01)
            return

        logger.info("Warmup: probando síntesis...")
        
        try:
            # Warmup con una síntesis simple
            import numpy as np
            audio = self._model.generate(
                text=".",
                num_step=1,  # Mínimo para warmup
            )
            if audio and len(audio) > 0:
                logger.info("Warmup OK")
            else:
                logger.warning("Warmup: audio vacío")
        except Exception as e:
            logger.warning("Warmup falló: %s", e)

    def _get_mock_stock_voices(self) -> list[dict]:
        """Voces stock mock."""
        return [
            {"voice_id": "es-mx-male", "language": "es", "gender": "male", "name": "Spanish MX Male"},
            {"voice_id": "es-mx-female", "language": "es", "gender": "female", "name": "Spanish MX Female"},
            {"voice_id": "es-es-male", "language": "es", "gender": "male", "name": "Spanish Spain Male"},
            {"voice_id": "es-es-female", "language": "es", "gender": "female", "name": "Spanish Spain Female"},
            {"voice_id": "en-us-male", "language": "en", "gender": "male", "name": "English US Male"},
            {"voice_id": "en-us-female", "language": "en", "gender": "female", "name": "English US Female"},
            {"voice_id": "en-gb-male", "language": "en", "gender": "male", "name": "English UK Male"},
            {"voice_id": "en-gb-female", "language": "en", "gender": "female", "name": "English UK Female"},
            {"voice_id": "fr-fr-male", "language": "fr", "gender": "male", "name": "French Male"},
            {"voice_id": "fr-fr-female", "language": "fr", "gender": "female", "name": "French Female"},
            {"voice_id": "de-de-male", "language": "de", "gender": "male", "name": "German Male"},
            {"voice_id": "de-de-female", "language": "de", "gender": "female", "name": "German Female"},
            {"voice_id": "it-it-male", "language": "it", "gender": "male", "name": "Italian Male"},
            {"voice_id": "it-it-female", "language": "it", "gender": "female", "name": "Italian Female"},
            {"voice_id": "pt-br-male", "language": "pt", "gender": "male", "name": "Portuguese BR Male"},
            {"voice_id": "pt-br-female", "language": "pt", "gender": "female", "name": "Portuguese BR Female"},
            {"voice_id": "zh-cn-male", "language": "zh", "gender": "male", "name": "Chinese Male"},
            {"voice_id": "zh-cn-female", "language": "zh", "gender": "female", "name": "Chinese Female"},
            {"voice_id": "ja-jp-male", "language": "ja", "gender": "male", "name": "Japanese Male"},
            {"voice_id": "ja-jp-female", "language": "ja", "gender": "female", "name": "Japanese Female"},
            {"voice_id": "ko-kr-male", "language": "ko", "gender": "male", "name": "Korean Male"},
            {"voice_id": "ko-kr-female", "language": "ko", "gender": "female", "name": "Korean Male"},
        ]

    def _emotion_to_instruct(self, emotion: str | None, intensity: float | None = None) -> str | None:
        """Convierte emoción a instrucción de voz."""
        if not emotion:
            return None
        
        intensity_suffix = ""
        if intensity is not None:
            if intensity > 0.7:
                intensity_suffix = ", very expressive"
            elif intensity < 0.3:
                intensity_suffix = ", subtle"
        
        emotion_map = {
            "neutral": "neutral tone",
            "happy": "happy" + intensity_suffix,
            "sad": "sad" + intensity_suffix,
            "angry": "angry" + intensity_suffix,
            "surprised": "surprised" + intensity_suffix,
        }
        
        return emotion_map.get(emotion)

    def _build_instruct(self, voice_id: str, emotion: str | None = None, intensity: float | None = None) -> str:
        """Construye la instrucción completa para voice design."""
        base_instruct = STOCK_VOICE_INSTRUCTS.get(voice_id, "natural voice")
        
        emotion_instruct = self._emotion_to_instruct(emotion, intensity)
        if emotion_instruct:
            return f"{base_instruct}, {emotion_instruct}"
        
        return base_instruct

    def _numpy_to_wav(self, audio: list) -> bytes:
        """Convierte lista de numpy arrays a WAV bytes."""
        import numpy as np
        
        if not audio or len(audio) == 0:
            raise EngineUnavailableError("El modelo no generó audio")
        
        # Concatenar todos los chunks
        audio_data = np.concatenate(audio) if len(audio) > 1 else audio[0]
        
        # Normalizar a float32 en rango [-1, 1] si es necesario
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Escalar a int16 para WAV
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # Escribir a BytesIO como WAV (24 kHz, 1 canal)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(24000)
            wav_file.writeframes(audio_int16.tobytes())
        
        return buffer.getvalue()

    async def synthesize_stock(
        self,
        *,
        text: str,
        voice_id: str,
        language: str | None = None,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        """Sintetiza con voz stock (voice design)."""
        logger.debug("synthesize_stock: voice_id=%s, text_len=%d", voice_id, len(text))

        # Verificar que la voz existe
        voice = next((v for v in self._stock_voices if v["voice_id"] == voice_id), None)
        if not voice:
            raise VoiceNotFoundError(voice_id, "stock")

        # Validar emoción
        if emotion and emotion not in self._emotions:
            raise UnsupportedEmotionError(emotion, self._emotions)

        if self._use_mock:
            return self._generate_test_tone_wav(
                duration_sec=max(0.5, len(text) * 0.08),
                sample_rate=22050,
                frequency=440.0,
                amplitude=0.3,
            )

        # Modo REAL: usar voice design
        instruct = self._build_instruct(voice_id, emotion, intensity)
        
        try:
            # Ejecutar en thread pool para no bloquear
            audio = await asyncio.to_thread(
                self._model.generate,
                text=text,
                instruct=instruct,
                speed=speed,
            )
            
            return self._numpy_to_wav(audio)
            
        except Exception as e:
            logger.error("Error en synthesize_stock: %s", e)
            raise EngineUnavailableError(f"Error sintetizando: {e}")

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: str,
        language: str | None = None,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        """Sintetiza con voz clonada."""
        logger.debug("synthesize_clone: ref=%s, text_len=%d", reference_audio_path, len(text))

        import os
        if not self._use_mock and not os.path.exists(reference_audio_path):
            raise EngineUnavailableError(f"Reference audio no encontrado: {reference_audio_path}")

        # Validar emoción
        if emotion and emotion not in self._emotions:
            raise UnsupportedEmotionError(emotion, self._emotions)

        if self._use_mock:
            return self._generate_test_tone_wav(
                duration_sec=max(0.5, len(text) * 0.08),
                sample_rate=22050,
                frequency=880.0,
                amplitude=0.3,
            )

        # Modo REAL: usar voice cloning
        try:
            # Ejecutar en thread pool para no bloquear
            audio = await asyncio.to_thread(
                self._model.generate,
                text=text,
                ref_audio=reference_audio_path,
            )
            
            return self._numpy_to_wav(audio)
            
        except Exception as e:
            logger.error("Error en synthesize_clone: %s", e)
            raise EngineUnavailableError(f"Error sintetizando con voz clonada: {e}")

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        """Lista voces stock."""
        voices = self._stock_voices
        if language:
            voices = [v for v in voices if v["language"] == language]
        return voices

    async def list_emotions(self) -> list[str]:
        """Lista emociones."""
        return self._emotions.copy()

    async def health_check(self) -> dict:
        """Estado del motor."""
        gpu_available = False
        vram_free_mb = 0
        device_info = "cpu"

        try:
            gpu_available = torch.cuda.is_available()
            if gpu_available:
                vram_free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024)
                device_info = f"cuda:{torch.cuda.current_device()}"
        except Exception:
            pass

        return {
            "model_loaded": self._model is not None,
            "gpu_available": gpu_available,
            "device": device_info,
            "stock_voices_count": len(self._stock_voices),
            "vram_free_mb": vram_free_mb,
            "mode": "MOCK" if self._use_mock else "REAL",
        }

    def _generate_test_tone_wav(
        self,
        duration_sec: float = 1.0,
        sample_rate: int = 22050,
        frequency: float = 440.0,
        amplitude: float = 0.3,
    ) -> bytes:
        """Genera WAV con tono senoidal (para modo mock)."""
        num_samples = int(duration_sec * sample_rate)
        max_amplitude = 32767

        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            value = amplitude * math.sin(2 * math.pi * frequency * t)
            sample = int(max_amplitude * value)
            samples.append(struct.pack('<h', sample))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b''.join(samples))

        return buffer.getvalue()


_engine_instance: OmniVoiceEngine | None = None


async def get_engine() -> OmniVoiceEngine:
    """Obtiene la instancia singleton del motor."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OmniVoiceEngine()
        await _engine_instance.initialize()
    return _engine_instance


async def close_engine() -> None:
    """Cierra el motor."""
    global _engine_instance
    if _engine_instance is not None:
        _engine_instance = None
